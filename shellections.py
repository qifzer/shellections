import json
import curses
import calendar
from datetime import datetime, timedelta
import requests
import os
import random
import signal
import sys
import time

# Load the data from the JSON file
def download_connections_json():
    url = "https://raw.githubusercontent.com/Eyefyre/NYT-Connections-Answers/main/connections.json"
    response = requests.get(url)
    if response.status_code == 200:
        with open('connections.json', 'w') as f:
            f.write(response.text)
        return True
    return False

def check_for_updates():
    if not os.path.exists('connections.json'):
        return download_connections_json()

    url = "https://api.github.com/repos/Eyefyre/NYT-Connections-Answers/commits?path=connections.json&page=1&per_page=1"
    response = requests.get(url)
    if response.status_code == 200:
        latest_commit_date = datetime.strptime(response.json()[0]['commit']['committer']['date'], "%Y-%m-%dT%H:%M:%SZ")
        local_file_date = datetime.fromtimestamp(os.path.getmtime('connections.json'))
        if latest_commit_date > local_file_date:
            return download_connections_json()
    return False

def load_puzzle_data():
    if check_for_updates():
        print("Downloaded or updated connections.json")
    with open('connections.json', 'r') as f:
        return json.load(f)

# Create a dictionary to quickly look up puzzles by date
puzzle_data = load_puzzle_data()
puzzle_dict = {puzzle['date']: puzzle for puzzle in puzzle_data}

# Define colors
YELLOW = 1
BLUE = 2
GREEN = 3
PURPLE = 4
WHITE = 5
BLACK = 6
RED = 7

# Define themes
THEMES = {
    "black": {
        "bg": curses.COLOR_BLACK,
        "fg": curses.COLOR_WHITE,
        "yellow": curses.COLOR_YELLOW,
        "blue": curses.COLOR_BLUE,
        "green": curses.COLOR_GREEN,
        "purple": curses.COLOR_MAGENTA,
        "red": curses.COLOR_RED,
    },
    "default": {
        "bg": -1,  # Use default terminal background
        "fg": -1,  # Use default terminal foreground
        "yellow": curses.COLOR_YELLOW,
        "blue": curses.COLOR_BLUE,
        "green": curses.COLOR_GREEN,
        "purple": curses.COLOR_MAGENTA,
        "red": curses.COLOR_RED,
    },
    "light": {
        "bg": curses.COLOR_WHITE,
        "fg": curses.COLOR_BLACK,
        "yellow": curses.COLOR_YELLOW,
        "blue": curses.COLOR_BLUE,
        "green": curses.COLOR_GREEN,
        "purple": curses.COLOR_MAGENTA,
        "red": curses.COLOR_RED,
    },
    "grey": {
        "bg": 235,  # Background #282A36
        "fg": 253,  # Foreground #F8F8F2
        "yellow": 228,  # Yellow #F1FA8C
        "blue": 117,  # Cyan #8BE9FD
        "green": 84,  # Green #50FA7B
        "purple": 141,  # Purple #BD93F9
        "red": curses.COLOR_RED,
    },
}

def setup_colors(stdscr, theme):
    curses.use_default_colors()
    
    bg = THEMES[theme]["bg"]
    fg = THEMES[theme]["fg"]
    
    curses.init_pair(YELLOW, THEMES[theme]["yellow"], bg)
    curses.init_pair(BLUE, THEMES[theme]["blue"], bg)
    curses.init_pair(GREEN, THEMES[theme]["green"], bg)
    curses.init_pair(PURPLE, THEMES[theme]["purple"], bg)
    curses.init_pair(WHITE, fg, bg)
    curses.init_pair(BLACK, bg, fg)
    curses.init_pair(RED, THEMES[theme]["red"], bg)

    # Set the default background color
    stdscr.bkgd(' ', curses.color_pair(WHITE))

def draw_centered_text(stdscr, y, text, color_pair=WHITE, attr=curses.A_NORMAL):
    height, width = stdscr.getmaxyx()
    x = (width - len(text)) // 2
    stdscr.attron(curses.color_pair(color_pair) | attr)
    stdscr.addstr(y, x, text)
    stdscr.attroff(curses.color_pair(color_pair) | attr)

def draw_calendar(stdscr, year, month, available_dates, selected_date, completed_dates):
    height, width = stdscr.getmaxyx()
    calendar.setfirstweekday(calendar.SUNDAY)
    cal = calendar.monthcalendar(year, month)

    # Draw month and year
    draw_centered_text(stdscr, 2, f"{calendar.month_name[month]} {year}", curses.color_pair(WHITE), curses.A_BOLD)

    # Draw weekday headers
    weekdays = "Su Mo Tu We Th Fr Sa"
    draw_centered_text(stdscr, 4, weekdays, curses.color_pair(WHITE), curses.A_UNDERLINE)

    cal_width = 20
    cal_height = 8
    start_y = (height - cal_height) // 2
    start_x = (width - cal_width) // 2

    for week_num, week in enumerate(cal):
        for day_num, day in enumerate(week):
            if day != 0:
                date_str = f"{year}-{month:02d}-{day:02d}"
                x = start_x + day_num * 3
                y = start_y + week_num
                if date_str == selected_date:
                    stdscr.addstr(y, x, f"{day:2d}", curses.color_pair(PURPLE) | curses.A_BOLD)
                elif date_str in completed_dates:
                    stdscr.addstr(y, x, f"{day:2d}", curses.color_pair(YELLOW))
                elif date_str in available_dates:
                    stdscr.addstr(y, x, f"{day:2d}", curses.color_pair(GREEN))
                else:
                    stdscr.addstr(y, x, f"{day:2d}", curses.color_pair(WHITE))

def load_options():
    default_options = {'track_completed': True, 'show_stats': True, 'theme': 'black'}
    if os.path.exists('options.json'):
        with open('options.json', 'r') as f:
            loaded_options = json.load(f)
        # Update default options with loaded options, ensuring all keys are present
        default_options.update(loaded_options)
    return default_options

def save_options(options):
    default_options = {'track_completed': True, 'show_stats': True, 'theme': 'black'}
    # Ensure all keys are present before saving
    options_to_save = default_options.copy()
    options_to_save.update(options)
    with open('options.json', 'w') as f:
        json.dump(options_to_save, f)

def load_stats():
    if os.path.exists('stats.json'):
        with open('stats.json', 'r') as f:
            return json.load(f)
    return {'completed_dates': [], 'total_played': 0, 'total_won': 0}

def save_stats(stats):
    with open('stats.json', 'w') as f:
        json.dump(stats, f)

def draw_options_menu(stdscr, options):
    stdscr.clear()
    height, width = stdscr.getmaxyx()

    draw_centered_text(stdscr, 2, "Options", curses.color_pair(WHITE), curses.A_BOLD)
    draw_centered_text(stdscr, 4, f"1. Track completed puzzles: {'On' if options['track_completed'] else 'Off'}", curses.color_pair(WHITE))
    draw_centered_text(stdscr, 5, f"2. Show stats menu: {'On' if options['show_stats'] else 'Off'}", curses.color_pair(WHITE))
    draw_centered_text(stdscr, 6, f"3. Theme: {options['theme']}", curses.color_pair(WHITE))
    draw_centered_text(stdscr, 8, "Press the number to change an option, or any other key to return", curses.color_pair(WHITE))

    key = stdscr.getch()
    if key == ord('1'):
        options['track_completed'] = not options['track_completed']
    elif key == ord('2'):
        options['show_stats'] = not options['show_stats']
    elif key == ord('3'):
        themes = list(THEMES.keys())
        current_index = themes.index(options['theme'])
        options['theme'] = themes[(current_index + 1) % len(themes)]
        setup_colors(stdscr, options['theme'])
        stdscr.clear()
        stdscr.refresh()

    save_options(options)

def draw_stats_menu(stdscr, stats):
    stdscr.clear()
    height, width = stdscr.getmaxyx()

    draw_centered_text(stdscr, 2, "Stats", curses.color_pair(WHITE), curses.A_BOLD)
    draw_centered_text(stdscr, 4, f"Total puzzles played: {stats['total_played']}", curses.color_pair(WHITE))
    draw_centered_text(stdscr, 5, f"Total puzzles won: {stats['total_won']}", curses.color_pair(WHITE))
    draw_centered_text(stdscr, 6, f"Win rate: {stats['total_won'] / stats['total_played'] * 100:.2f}%" if stats['total_played'] > 0 else "Win rate: N/A", curses.color_pair(WHITE))
    draw_centered_text(stdscr, 8, "Press any key to return", curses.color_pair(WHITE))

    stdscr.getch()

def check_terminal_size(stdscr, min_height, min_width):
    height, width = stdscr.getmaxyx()
    if height < min_height or width < min_width:
        stdscr.clear()
        message = f"Terminal too small. Minimum size: {min_width}x{min_height}. Current size: {width}x{height}"
        try:
            stdscr.addstr(0, 0, message)
            stdscr.refresh()
            stdscr.getch()
        except curses.error:
            pass
        return False
    return True

def play_puzzle(stdscr, puzzle, stats, infinite_tries=False):
    if not check_terminal_size(stdscr, 18, 80):
        return

    all_words = []
    for group in puzzle['answers']:
        all_words.extend(group['members'])

    random.shuffle(all_words)  # Shuffle words initially

    selected_words = []
    correct_groups = []
    mistakes_remaining = 4 if not infinite_tries else float('inf')
    attempts_used = 0

    cursor_pos = [0, 0]

    start_time = time.time()
    attempts = []

    while mistakes_remaining > 0 and len(correct_groups) < 4:
        stdscr.clear()
        height, width = stdscr.getmaxyx()

        draw_centered_text(stdscr, 1, f"NYT Connections - {puzzle['date']}", curses.color_pair(WHITE), curses.A_BOLD)
        draw_centered_text(stdscr, 3, f"Mistakes remaining: {'∞' if infinite_tries else mistakes_remaining}", curses.color_pair(WHITE))

        # Display correct groups
        for i, group in enumerate(correct_groups):
            color = [YELLOW, GREEN, BLUE, PURPLE][i]
            draw_centered_text(stdscr, 5 + i, f"{group['group']}: {', '.join(group['members'])}", color)

        # Display remaining words
        remaining_words = [word for word in all_words if not any(word in group['members'] for group in correct_groups)]

        # Calculate grid dimensions
        grid_height = 7
        grid_width = 72

        start_y = (height - grid_height) // 2
        start_x = (width - grid_width) // 2

        # Ensure start positions are not negative
        start_y = max(1, start_y)
        start_x = max(1, start_x)

        # Calculate the number of rows needed
        num_rows = (len(remaining_words) + 3) // 4

        # Draw horizontal separators
        for i in range(num_rows + 1):
            separator = '+' + ('-' * 17 + '+') * 4
            stdscr.addstr(start_y + i * 2, start_x, separator[:width - start_x])

        # Display words
        for i, word in enumerate(remaining_words):
            y, x = divmod(i, 4)
            attr = curses.A_REVERSE if [y, x] == cursor_pos else curses.A_NORMAL
            display_y = start_y + y * 2 + 1
            display_x = start_x + x * 18

            if display_y < height - 1 and display_x + 18 < width:
                # Draw left vertical separator
                stdscr.addstr(display_y, display_x, '|')

                if word in selected_words:
                    stdscr.addstr(display_y, display_x + 1, f"[{word:^15}]", curses.color_pair(WHITE) | curses.A_BOLD | attr)
                else:
                    stdscr.addstr(display_y, display_x + 1, f" {word:^15} ", curses.color_pair(WHITE) | attr)

                # Draw right vertical separator
                stdscr.addstr(display_y, display_x + 18, '|')

        # Draw right-most vertical separator
        for i in range(num_rows):
            stdscr.addstr(start_y + i * 2 + 1, start_x + 72, '|')

        draw_centered_text(stdscr, height - 3, "Use h/j/k/l to move, SPACE to select, ENTER to submit, S to shuffle, Ctrl+S to solve.", curses.color_pair(WHITE))
        stdscr.refresh()

        # Handle input
        key = stdscr.getch()
        if key == ord('q'):
            return 'quit'
        elif key == 19:  # Ctrl+S
            correct_groups = puzzle['answers']
            break
        elif key in [ord('h'), curses.KEY_LEFT, ord('b')]:  # Left arrow, 'h', or 'b'
            cursor_pos[1] = max(0, cursor_pos[1] - 1)
        elif key in [ord('l'), curses.KEY_RIGHT, ord('f')]:  # Right arrow, 'l', or 'f'
            cursor_pos[1] = min(3, cursor_pos[1] + 1)
        elif key in [ord('k'), curses.KEY_UP, ord('p')]:  # Up arrow, 'k', or 'p'
            cursor_pos[0] = max(0, cursor_pos[0] - 1)
        elif key in [ord('j'), curses.KEY_DOWN, ord('n')]:  # Down arrow, 'j', or 'n'
            cursor_pos[0] = min(3, cursor_pos[0] + 1)
        elif key == ord(' '):  # SPACE key
            index = cursor_pos[0] * 4 + cursor_pos[1]
            if index < len(remaining_words):
                word = remaining_words[index]
                if word in selected_words:
                    selected_words.remove(word)
                elif len(selected_words) < 4:
                    selected_words.append(word)
        elif key in [ord('s'), ord('S')]:  # Shuffle functionality
            random.shuffle(all_words)
        elif key == 10 and len(selected_words) == 4:  # ENTER key
            attempts_used += 1
            attempts.append(selected_words.copy())
            # Check if the selection is correct
            correct_group = None
            for group in puzzle['answers']:
                if set(selected_words) == set(group['members']):
                    correct_group = group
                    break

            if correct_group:
                correct_groups.append(correct_group)
            else:
                # Check for 3 out of 4 matches here
                for group in puzzle['answers']:
                    matches = sum(1 for word in selected_words if word in group['members'])
                    if matches == 3:
                        draw_centered_text(stdscr, height - 4, "You've matched 3 out of 4 in a group!", YELLOW, curses.A_BOLD)
                        stdscr.refresh()
                        stdscr.getch()  # Wait for user input before continuing
                        break

            if not correct_group and not infinite_tries:
                mistakes_remaining -= 1

            selected_words = []

        if mistakes_remaining == 0 or len(correct_groups) == 4:
            break

    end_time = time.time()
    completion_time = end_time - start_time

    # Game over screen
    stdscr.clear()
    if len(correct_groups) == 4:
        draw_centered_text(stdscr, height // 2 - 4, "Congratulations! You solved the puzzle!", GREEN)
        stats['total_won'] += 1
    else:
        draw_centered_text(stdscr, height // 2 - 4, "Game Over! Here are the correct answers:", WHITE)

    for i, group in enumerate(puzzle['answers']):
        color = [YELLOW, GREEN, BLUE, PURPLE][i]
        draw_centered_text(stdscr, height // 2 - 2 + i * 2, f"{group['group']}: {', '.join(group['members'])}", color)

    stats['total_played'] += 1
    stats['completed_dates'].append(puzzle['date'])
    save_stats(stats)

    draw_centered_text(stdscr, height - 2, "Press 'v' to view results, any other key to continue, or 'q' to quit...", curses.color_pair(WHITE))
    key = stdscr.getch()
    if key == ord('q'):
        return 'quit'
    elif key == ord('v'):
        show_results(stdscr, puzzle, attempts, completion_time, len(correct_groups) == 4)

def show_results(stdscr, puzzle, attempts, completion_time, solved):
    stdscr.clear()
    height, width = stdscr.getmaxyx()

    draw_centered_text(stdscr, 2, "Connections Results", curses.color_pair(WHITE), curses.A_BOLD)

    if solved:
        draw_centered_text(stdscr, 4, f"Puzzle solved in {completion_time:.2f} seconds!", curses.color_pair(GREEN))
    else:
        draw_centered_text(stdscr, 4, f"Puzzle not solved. Time spent: {completion_time:.2f} seconds", curses.color_pair(RED))

    draw_centered_text(stdscr, 6, f"Total attempts: {len(attempts)}", curses.color_pair(WHITE))

    for i, attempt in enumerate(attempts, start=1):
        attempt_str = f"Attempt {i}: {', '.join(attempt)}"
        y = 8 + i
        if y < height - 3:
            draw_centered_text(stdscr, y, attempt_str, curses.color_pair(WHITE))

    draw_centered_text(stdscr, height - 2, "Press any key to continue...", curses.color_pair(WHITE))
    stdscr.getch()

def main(stdscr):
    if not check_terminal_size(stdscr, 18, 80):
        return

    curses.curs_set(0)
    options = load_options()
    setup_colors(stdscr, options['theme'])
    stdscr.clear()
    stdscr.refresh()

    available_dates = set(puzzle_dict.keys())
    current_date = datetime.now()
    year, month = current_date.year, current_date.month
    selected_date = current_date.strftime("%Y-%m-%d")

    earliest_date = min(datetime.strptime(date, "%Y-%m-%d") for date in available_dates)
    latest_date = max(datetime.strptime(date, "%Y-%m-%d") for date in available_dates)

    stats = load_stats()

    infinite_tries = False

    while True:
        stdscr.clear()
        draw_calendar(stdscr, year, month, available_dates, selected_date, set(stats['completed_dates']))
        height, width = stdscr.getmaxyx()
        draw_centered_text(stdscr, height - 6, "Use h/j/k/l to navigate, ENTER to select a date", curses.color_pair(WHITE))
        
        options_text = "r: Random date, o: Options"
        if options['show_stats']:
            options_text += ", s: Stats"
        options_text += ", i: Toggle infinite tries, q: Quit"
        draw_centered_text(stdscr, height - 5, options_text, curses.color_pair(WHITE))
        draw_centered_text(stdscr, height - 4, f"Infinite tries: {'On' if infinite_tries else 'Off'}", curses.color_pair(WHITE))

        key = stdscr.getch()

        if key == ord('q'):
            break
        elif key in [ord('h'), curses.KEY_LEFT, ord('b')]:  # Left arrow, 'h', or 'b'
            current_date -= timedelta(days=1)
        elif key in [ord('l'), curses.KEY_RIGHT, ord('f')]:  # Right arrow, 'l', or 'f'
            current_date += timedelta(days=1)
        elif key in [ord('k'), curses.KEY_UP, ord('p')]:  # Up arrow, 'k', or 'p'
            current_date -= timedelta(days=7)
        elif key in [ord('j'), curses.KEY_DOWN, ord('n')]:  # Down arrow, 'j', or 'n'
            current_date += timedelta(days=7)
        elif key == ord('r'):
            current_date = datetime.strptime(random.choice(list(available_dates)), "%Y-%m-%d")
        elif key == ord('o'):
            draw_options_menu(stdscr, options)
        elif key == ord('s'):
            if options['show_stats']:
                draw_stats_menu(stdscr, stats)
        elif key == ord('i'):
            infinite_tries = not infinite_tries
        elif key == ord('0'):
            current_date = earliest_date
        elif key == ord('$'):
            current_date = latest_date
        elif key == 10:  # ENTER key
            if selected_date in puzzle_dict:
                result = play_puzzle(stdscr, puzzle_dict[selected_date], stats, infinite_tries)
                if result == 'quit':
                    break
            else:
                draw_centered_text(stdscr, height - 6, "No puzzle available for this date.", curses.color_pair(YELLOW))
                stdscr.getch()

        year, month = current_date.year, current_date.month
        selected_date = current_date.strftime("%Y-%m-%d")

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        curses.wrapper(main)
    except curses.error:
        print("An error occurred. Make sure your terminal is at least 80x18 characters.")
        sys.exit(1)
