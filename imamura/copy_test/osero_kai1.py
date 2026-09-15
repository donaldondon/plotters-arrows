import pygame
import sys
import math
import random

# 画面サイズを自由に設定可能（正方形）
BOARD_SIZE = 500
INFO_BAR_HEIGHT = 100
SCREEN_WIDTH, SCREEN_HEIGHT = BOARD_SIZE, BOARD_SIZE + INFO_BAR_HEIGHT

ROWS, COLS = 8, 8
CELL_SIZE = BOARD_SIZE // COLS
BOARD_COLOR = (0, 128, 0)
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
HINT_COLOR = (100, 200, 255)

EMPTY = 0
BLACK_PIECE = 1
WHITE_PIECE = 2

DIRECTIONS = [(-1, -1), (-1, 0), (-1, 1),
              (0, -1),          (0, 1),
              (1, -1),  (1, 0), (1, 1)]

# CPUの強さ調整用の位置評価テーブル（角や辺を重視）
POSITION_WEIGHTS = [
    [100, -20, 10,  5,  5, 10, -20, 100],
    [-20, -50, -2, -2, -2, -2, -50, -20],
    [10,  -2,  -1, -1, -1, -1,  -2,  10],
    [5,   -2,  -1, -1, -1, -1,  -2,   5],
    [5,   -2,  -1, -1, -1, -1,  -2,   5],
    [10,  -2,  -1, -1, -1, -1,  -2,  10],
    [-20, -50, -2, -2, -2, -2, -50, -20],
    [100, -20, 10,  5,  5, 10, -20, 100],
]

# CPUの難易度ごとの探索の深さ（レベル3のみ使用）
CPU_SEARCH_DEPTH = 4

pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("オセロ")
font = pygame.font.SysFont("msgothic", CELL_SIZE // 2)
menu_font = pygame.font.SysFont("msgothic", 26)

def init_board():
    board = [[EMPTY for _ in range(COLS)] for _ in range(ROWS)]
    board[3][3] = WHITE_PIECE
    board[3][4] = BLACK_PIECE
    board[4][3] = BLACK_PIECE
    board[4][4] = WHITE_PIECE
    return board

def on_board(x, y):
    return 0 <= x < ROWS and 0 <= y < COLS

def other_player(player):
    return WHITE_PIECE if player == BLACK_PIECE else BLACK_PIECE

def valid_moves(board, player):
    return [(x, y) for x in range(ROWS) for y in range(COLS)
            if board[x][y] == EMPTY and is_valid_move(board, player, x, y)]

def is_valid_move(board, player, x, y):
    opponent = other_player(player)
    if board[x][y] != EMPTY:
        return False
    for dx, dy in DIRECTIONS:
        nx, ny = x + dx, y + dy
        if on_board(nx, ny) and board[nx][ny] == opponent:
            while on_board(nx, ny) and board[nx][ny] == opponent:
                nx += dx
                ny += dy
            if on_board(nx, ny) and board[nx][ny] == player:
                return True
    return False

def make_move(board, player, x, y):
    if not is_valid_move(board, player, x, y):
        return False
    board[x][y] = player
    opponent = other_player(player)
    for dx, dy in DIRECTIONS:
        nx, ny = x + dx, y + dy
        to_flip = []
        while on_board(nx, ny) and board[nx][ny] == opponent:
            to_flip.append((nx, ny))
            nx += dx
            ny += dy
        if on_board(nx, ny) and board[nx][ny] == player:
            for fx, fy in to_flip:
                board[fx][fy] = player
    return True

def count_stones(board):
    black = sum(row.count(BLACK_PIECE) for row in board)
    white = sum(row.count(WHITE_PIECE) for row in board)
    return black, white

def clone_board(board):
    return [row[:] for row in board]

# ---------------------------------------------------------------------------
# CPU対戦モード用のロジック
# ---------------------------------------------------------------------------

def evaluate_board(board, player):
    """盤面をplayerの視点で評価するヒューリスティック関数（レベル3で使用）"""
    opponent = other_player(player)
    score = 0
    for x in range(ROWS):
        for y in range(COLS):
            if board[x][y] == player:
                score += POSITION_WEIGHTS[x][y]
            elif board[x][y] == opponent:
                score -= POSITION_WEIGHTS[x][y]

    # 着手可能数(モビリティ)も評価に加える
    my_moves = len(valid_moves(board, player))
    opp_moves = len(valid_moves(board, opponent))
    score += (my_moves - opp_moves) * 2
    return score

def minimax(board, depth, player_to_move, maximizer, alpha, beta):
    """アルファベータ法によるミニマックス探索。(評価値, 手) を返す"""
    moves = valid_moves(board, player_to_move)

    if depth == 0 or (not moves and not valid_moves(board, other_player(player_to_move))):
        return evaluate_board(board, maximizer), None

    if not moves:
        # 打てる手がない場合はパス
        score, _ = minimax(board, depth - 1, other_player(player_to_move), maximizer, alpha, beta)
        return score, None

    best_move = None
    if player_to_move == maximizer:
        best_score = -math.inf
        for (x, y) in moves:
            next_board = clone_board(board)
            make_move(next_board, player_to_move, x, y)
            score, _ = minimax(next_board, depth - 1, other_player(player_to_move), maximizer, alpha, beta)
            if score > best_score:
                best_score = score
                best_move = (x, y)
            alpha = max(alpha, best_score)
            if alpha >= beta:
                break
        return best_score, best_move
    else:
        best_score = math.inf
        for (x, y) in moves:
            next_board = clone_board(board)
            make_move(next_board, player_to_move, x, y)
            score, _ = minimax(next_board, depth - 1, other_player(player_to_move), maximizer, alpha, beta)
            if score < best_score:
                best_score = score
                best_move = (x, y)
            beta = min(beta, best_score)
            if alpha >= beta:
                break
        return best_score, best_move

def cpu_choose_move(board, player, level):
    """CPUの難易度(1:弱い, 2:普通, 3:強い)に応じて手を選ぶ"""
    moves = valid_moves(board, player)
    if not moves:
        return None

    if level == 1:
        # レベル1: ランダムに手を選ぶ
        return random.choice(moves)

    elif level == 2:
        # レベル2: その手で取れる石の数が最も多い手を選ぶ（同数ならランダム）
        best_moves = []
        best_count = -1
        for (x, y) in moves:
            next_board = clone_board(board)
            make_move(next_board, player, x, y)
            black, white = count_stones(next_board)
            gained = black if player == BLACK_PIECE else white
            if gained > best_count:
                best_count = gained
                best_moves = [(x, y)]
            elif gained == best_count:
                best_moves.append((x, y))
        return random.choice(best_moves)

    else:
        # レベル3: ミニマックス探索(アルファベータ法)で最善手を選ぶ
        _, move = minimax(board, CPU_SEARCH_DEPTH, player, player, -math.inf, math.inf)
        return move if move is not None else random.choice(moves)

def select_mode():
    """起動時にモード（2人対戦 / CPU対戦のレベル）を選択する画面"""
    buttons = []

    def build_buttons():
        buttons.clear()
        btn_2p = pygame.Rect(SCREEN_WIDTH // 2 - 130, 90, 260, 50)
        buttons.append((("2p", None), btn_2p, "2人対戦"))

        labels = [
            ("cpu", 1, "CPU対戦 レベル1（弱い）"),
            ("cpu", 2, "CPU対戦 レベル2（普通）"),
            ("cpu", 3, "CPU対戦 レベル3（強い）"),
        ]
        for i, (mode, level, label) in enumerate(labels):
            rect = pygame.Rect(SCREEN_WIDTH // 2 - 130, 170 + i * 70, 260, 50)
            buttons.append(((mode, level), rect, label))

    build_buttons()

    while True:
        screen.fill((30, 30, 30))
        title = menu_font.render("モードを選択してください", True, WHITE)
        screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 30))

        for (mode, level), rect, label in buttons:
            color = (70, 70, 200) if mode == "2p" else (180, 70, 70)
            pygame.draw.rect(screen, color, rect, border_radius=8)
            text = menu_font.render(label, True, WHITE)
            screen.blit(text, (rect.centerx - text.get_width() // 2,
                                rect.centery - text.get_height() // 2))

        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = pygame.mouse.get_pos()
                for (mode, level), rect, label in buttons:
                    if rect.collidepoint(mx, my):
                        return mode, level

def animate_piece(x, y, color):
    center = (y * CELL_SIZE + CELL_SIZE // 2, x * CELL_SIZE + CELL_SIZE // 2)
    for scale in range(2, 21):
        radius = int((CELL_SIZE // 2 - 4) * scale / 20)
        draw_board(current_board, valid_moves(current_board, current_player))
        pygame.draw.circle(screen, color, center, radius)
        pygame.display.flip()
        pygame.time.delay(8)

def draw_board(board, valid_moves_list):
    screen.fill(BOARD_COLOR)

    # グリッド
    for x in range(ROWS):
        for y in range(COLS):
            rect = pygame.Rect(y * CELL_SIZE, x * CELL_SIZE, CELL_SIZE, CELL_SIZE)
            pygame.draw.rect(screen, BLACK, rect, 1)

    # ヒント表示
    for x, y in valid_moves_list:
        hint_center = (y * CELL_SIZE + CELL_SIZE // 2, x * CELL_SIZE + CELL_SIZE // 2)
        pygame.draw.circle(screen, HINT_COLOR, hint_center, 6)

    # 駒の描画
    for x in range(ROWS):
        for y in range(COLS):
            center = (y * CELL_SIZE + CELL_SIZE // 2, x * CELL_SIZE + CELL_SIZE // 2)
            if board[x][y] == BLACK_PIECE:
                pygame.draw.circle(screen, BLACK, center, CELL_SIZE // 2 - 4)
            elif board[x][y] == WHITE_PIECE:
                pygame.draw.circle(screen, WHITE, center, CELL_SIZE // 2 - 4)

    # スコア・手番バー
    pygame.draw.rect(screen, (50, 50, 50), (0, BOARD_SIZE, SCREEN_WIDTH, INFO_BAR_HEIGHT))
    black, white = count_stones(board)
    text1 = font.render(f"黒: {black}   白: {white}", True, WHITE)
    text2 = font.render(f"手番: {'黒' if current_player == BLACK_PIECE else '白'}", True, WHITE)
    screen.blit(text1, (20, BOARD_SIZE + 20))
    screen.blit(text2, (SCREEN_WIDTH - 160, BOARD_SIZE + 20))

def show_winner(board):
    black, white = count_stones(board)
    pygame.draw.rect(screen, (0, 0, 0), (0, BOARD_SIZE // 2 - 50, SCREEN_WIDTH, 100))
    if black > white:
        msg = "黒の勝ち！"
        color = WHITE
    elif white > black:
        msg = "白の勝ち！"
        color = WHITE
    else:
        msg = "引き分け！"
        color = (255, 255, 0)

    result_text = font.render(msg, True, color)
    screen.blit(result_text, (SCREEN_WIDTH // 2 - result_text.get_width() // 2,
                              BOARD_SIZE // 2 - result_text.get_height() // 2))
    pygame.display.flip()
    pygame.time.wait(3000)

# ゲームの状態
current_board = init_board()
current_player = BLACK_PIECE

def main():
    global current_player

    mode, level = select_mode()
    cpu_enabled = (mode == "cpu")
    cpu_player = WHITE_PIECE  # CPUは常に白（後手）を担当する

    while True:
        valid_list = valid_moves(current_board, current_player)
        draw_board(current_board, valid_list)
        pygame.display.flip()

        is_cpu_turn = cpu_enabled and current_player == cpu_player

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            elif event.type == pygame.MOUSEBUTTONDOWN and not is_cpu_turn:
                mx, my = pygame.mouse.get_pos()
                if my > BOARD_SIZE:
                    continue
                x, y = my // CELL_SIZE, mx // CELL_SIZE
                if (x, y) in valid_list:
                    make_move(current_board, current_player, x, y)
                    animate_piece(x, y, BLACK if current_player == BLACK_PIECE else WHITE)
                    current_player = other_player(current_player)

                    if not valid_moves(current_board, current_player):
                        current_player = other_player(current_player)
                        if not valid_moves(current_board, current_player):
                            draw_board(current_board, [])
                            pygame.display.flip()
                            show_winner(current_board)
                            return

        # CPUの手番であれば自動で着手する
        if is_cpu_turn and valid_list:
            pygame.time.delay(400)  # 少し間を置いて着手する
            move = cpu_choose_move(current_board, current_player, level)
            if move is not None:
                x, y = move
                make_move(current_board, current_player, x, y)
                animate_piece(x, y, WHITE if current_player == WHITE_PIECE else BLACK)
                current_player = other_player(current_player)

                if not valid_moves(current_board, current_player):
                    current_player = other_player(current_player)
                    if not valid_moves(current_board, current_player):
                        draw_board(current_board, [])
                        pygame.display.flip()
                        show_winner(current_board)
                        return

if __name__ == "__main__":
    main()
