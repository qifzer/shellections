import json
import curses
import calendar
from datetime import datetime, timedelta
import unicodedata
import requests
import os
import random
import signal

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

def setup_colors():
    curses.init_pair(YELLOW, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(BLUE, curses.COLOR_BLUE, curses.COLOR_BLACK)
    curses.init_pair(GREEN, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(PURPLE, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
    curses.init_pair(WHITE, curses.COLOR_WHITE, curses.COLOR_BLACK)
    curses.init_pair(BLACK, curses.COLOR_BLACK, curses.COLOR_WHITE)

def draw_centered_text(stdscr, y, text, color_pair=WHITE, attr=curses.A_NORMAL):
    height, width = stdscr.getmaxyx()
    if y < 0 or y >= height:
        return  # Don't draw if y is out of bounds
    x = max(0, (width - len(text)) // 2)
    text = text[:width]  # Truncate text if it's too long
    try:
        stdscr.addstr(y, x, text, color_pair | attr)
    except curses.error:
        pass  # Ignore errors if we can't write to the screen

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
    if os.path.exists('options.json'):
        with open('options.json', 'r') as f:
            return json.load(f)
    return {'track_completed': True, 'show_stats': True}

def save_options(options):
    with open('options.json', 'w') as f:
        json.dump(options, f)

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
    draw_centered_text(stdscr, 7, "Press the number to toggle an option, or any other key to return", curses.color_pair(WHITE))

    key = stdscr.getch()
    if key == ord('1'):
        options['track_completed'] = not options['track_completed']
    elif key == ord('2'):
        options['show_stats'] = not options['show_stats']

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

def play_puzzle(stdscr, puzzle, stats, infinite_tries=False):
    all_words = []
    for group in puzzle['answers']:
        all_words.extend(group['members'])

    random.shuffle(all_words)  # Shuffle words initially

    selected_words = []
    correct_groups = []
    mistakes_remaining = 4 if not infinite_tries else float('inf')
    attempts_used = 0
    emoji_representation = []

    cursor_pos = [0, 0]

    while mistakes_remaining > 0 and len(correct_groups) < 4:
        stdscr.clear()
        height, width = stdscr.getmaxyx()

        draw_centered_text(stdscr, 1, f"NYT Connections - {puzzle['date']}", curses.color_pair(WHITE), curses.A_BOLD)
        draw_centered_text(stdscr, 3, f"Mistakes remaining: {'∞' if infinite_tries else mistakes_remaining}", curses.color_pair(WHITE))

        # Display correct groups
        for i, group in enumerate(correct_groups):
            color = [YELLOW, BLUE, GREEN, PURPLE][i]
            draw_centered_text(stdscr, 5 + i, f"{group['group']}: {', '.join(group['members'])}", curses.color_pair(color))

        # Display remaining words
        remaining_words = [word for word in all_words if not any(word in group['members'] for group in correct_groups)]

        # Calculate grid dimensions
        grid_height = min(7, height - 6)  # Ensure grid fits vertically
        grid_width = min(72, width - 2)   # Ensure grid fits horizontally

        start_y = max(1, (height - grid_height) // 2)
        start_x = max(1, (width - grid_width) // 2)

        # Draw horizontal separators
        for i in range((len(remaining_words) + 3) // 4 + 1):
            separator = '+' + ('-' * 17 + '+') * 4
            try:
                stdscr.addstr(start_y + i * 2, start_x, separator[:width - start_x])
            except curses.error:
                pass  # Ignore errors if we can't write to the screen

        # Display words
        for i, word in enumerate(remaining_words):
            y, x = divmod(i, 4)
            if y >= grid_height // 2:
                break  # Stop if we've run out of vertical space
            attr = curses.A_REVERSE if [y, x] == cursor_pos else curses.A_NORMAL
            display_y = start_y + y * 2 + 1
            display_x = start_x + x * 18

            if display_y < height - 1 and display_x + 18 < width:
                try:
                    stdscr.addstr(display_y, display_x, '|')
                    if word in selected_words:
                        stdscr.addstr(display_y, display_x + 1, f"[{word:^15}]", curses.color_pair(WHITE) | curses.A_BOLD | attr)
                    else:
                        stdscr.addstr(display_y, display_x + 1, f" {word:^15} ", curses.color_pair(WHITE) | attr)
                    stdscr.addstr(display_y, display_x + 18, '|')
                except curses.error:
                    pass  # Ignore errors if we can't write to the screen

        # Draw right-most vertical separator
        for i in range((len(remaining_words) + 3) // 4):
            try:
                stdscr.addstr(start_y + i * 2 + 1, start_x + 72, '|')
            except curses.error:
                pass  # Ignore errors if we can't write to the screen

        # Add this new section to check for 3 out of 4 matches
        if len(selected_words) == 4:
            for group in puzzle['answers']:
                matches = sum(1 for word in selected_words if word in group['members'])
                if matches == 3:
                    draw_centered_text(stdscr, height - 4, "You've matched 3 out of 4 in a group!", curses.color_pair(YELLOW) | curses.A_BOLD)
                    break

        draw_centered_text(stdscr, height - 3, "Use h/j/k/l to move, SPACE to select, ENTER to submit, S to shuffle, Ctrl+S to solve.", curses.color_pair(WHITE))
        stdscr.refresh()

        # Handle input
        key = stdscr.getch()
        if key == ord('q'):
            return 'quit'
        elif key == 19:  # Ctrl+S
            correct_groups = puzzle['answers']
            break
        elif key == ord('h') and cursor_pos[1] > 0:
            cursor_pos[1] -= 1
        elif key == ord('l') and cursor_pos[1] < 3:
            cursor_pos[1] += 1
        elif key == ord('k') and cursor_pos[0] > 0:
            cursor_pos[0] -= 1
        elif key == ord('j') and cursor_pos[0] < 3:
            cursor_pos[0] += 1
        elif key == ord(' '):  # SPACE key
            index = cursor_pos[0] * 4 + cursor_pos[1]
            if index < len(remaining_words):
                word = remaining_words[index]
                if word in selected_words:
                    selected_words.remove(word)
                elif len(selected_words) < 4:
                    selected_words.append(word)
        elif key == ord('s') or key == ord('S'):  # New shuffle functionality
            random.shuffle(all_words)
        elif key == 10 and len(selected_words) == 4:  # ENTER key
            attempts_used += 1
            # Check if the selection is correct
            for group in puzzle['answers']:
                if set(selected_words) == set(group['members']):
                    correct_groups.append(group)
                    break

            # Create emoji representation for this attempt
            attempt_emojis = []
            for word in selected_words:
                for i, group in enumerate(puzzle['answers']):
                    if word in group['members']:
                        attempt_emojis.append(["🟨", "🟦", "🟩", "🟪"][i])
                        break

            if len(correct_groups) > len(emoji_representation):
                emoji_representation.append(attempt_emojis)
            else:
                emoji_representation.append(["🟥", "🟥", "🟥", "🟥"])
                if not infinite_tries:
                    mistakes_remaining -= 1

            selected_words = []

        if mistakes_remaining == 0 or len(correct_groups) == 4:
            break

    # Game over screen
    stdscr.clear()
    if len(correct_groups) == 4:
        draw_centered_text(stdscr, height // 2 - 4, "Congratulations! You solved the puzzle!", curses.color_pair(GREEN))
        stats['total_won'] += 1
    else:
        draw_centered_text(stdscr, height // 2 - 4, "Game Over! Here are the correct answers:", curses.color_pair(WHITE))

    for i, group in enumerate(puzzle['answers']):
        color = [YELLOW, BLUE, GREEN, PURPLE][i]
        draw_centered_text(stdscr, height // 2 - 2 + i * 2, f"{group['group']}: {', '.join(group['members'])}", curses.color_pair(color))

    stats['total_played'] += 1
    stats['completed_dates'].append(puzzle['date'])
    save_stats(stats)

    draw_centered_text(stdscr, height - 2, "Press 'v' to view results, any other key to continue, or 'q' to quit...", curses.color_pair(WHITE))
    key = stdscr.getch()
    if key == ord('q'):
        return 'quit'
    elif key == ord('v'):
        show_results(stdscr, puzzle, emoji_representation)

def show_results(stdscr, puzzle, emoji_representation):
    stdscr.clear()
    height, width = stdscr.getmaxyx()

    draw_centered_text(stdscr, height // 2 - 4, "Connections", curses.color_pair(WHITE), curses.A_BOLD)

    for i, row in enumerate(emoji_representation):
        draw_centered_text(stdscr, height // 2 + i, ''.join(row), curses.color_pair(WHITE))

    draw_centered_text(stdscr, height - 2, "Press any key to continue...", curses.color_pair(WHITE))
    stdscr.getch()

def main(stdscr):
    curses.curs_set(0)
    setup_colors()

    # Define minimum required terminal size
    MIN_HEIGHT = 24
    MIN_WIDTH = 80

    while True:
        height, width = stdscr.getmaxyx()
        
        if height < MIN_HEIGHT or width < MIN_WIDTH:
            stdscr.clear()
            draw_centered_text(stdscr, height // 2 - 1, "Terminal window too small!", curses.color_pair(YELLOW) | curses.A_BOLD)
            draw_centered_text(stdscr, height // 2, f"Please resize to at least {MIN_WIDTH}x{MIN_HEIGHT}", curses.color_pair(WHITE))
            draw_centered_text(stdscr, height // 2 + 1, "Press 'q' to quit or any other key to retry", curses.color_pair(WHITE))
            
            key = stdscr.getch()
            if key == ord('q'):
                break
            else:
                continue

        # Rest of your existing main function code
        available_dates = set(puzzle_dict.keys())
        current_date = datetime.now()
        year, month = current_date.year, current_date.month
        selected_date = current_date.strftime("%Y-%m-%d")

        options = load_options()
        stats = load_stats()

        infinite_tries = False

        while True:
            stdscr.clear()
            draw_calendar(stdscr, year, month, available_dates, selected_date, set(stats['completed_dates']))
            draw_centered_text(stdscr, height - 4, "Use h/j/k/l to navigate, ENTER to select a date", curses.color_pair(WHITE))
            draw_centered_text(stdscr, height - 3, "r: Random date, o: Options, s: Stats, q: Quit", curses.color_pair(WHITE))

            key = stdscr.getch()

            if key == ord('q'):
                break
            elif key == ord('h'):
                current_date -= timedelta(days=1)
            elif key == ord('l'):
                current_date += timedelta(days=1)
            elif key == ord('k'):
                current_date -= timedelta(days=7)
            elif key == ord('j'):
                current_date += timedelta(days=7)
            elif key == ord('r'):
                current_date = datetime.strptime(random.choice(list(available_dates)), "%Y-%m-%d")
            elif key == ord('o'):
                draw_options_menu(stdscr, options)
            elif key == ord('s'):
                if options['show_stats']:
                    draw_stats_menu(stdscr, stats)
            elif key == 10:  # ENTER key
                if selected_date in puzzle_dict:
                    result = play_puzzle(stdscr, puzzle_dict[selected_date], stats, infinite_tries)
                    if result == 'quit':
                        break
                else:
                    draw_centered_text(stdscr, height - 5, "No puzzle available for this date.", curses.color_pair(1))
                    stdscr.getch()

            year, month = current_date.year, current_date.month
            selected_date = current_date.strftime("%Y-%m-%d")

        # Break out of the outer loop if we've exited the inner loop
        break

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    curses.wrapper(main)
