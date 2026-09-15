import pygame
import sys
import math

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

pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("オセロ")
font = pygame.font.SysFont("msgothic", CELL_SIZE // 2)

def init_board():
    board = [[EMPTY for _ in range(COLS)] for _ in range(ROWS)]
    board[3][3] = WHITE_PIECE
    board[3][4] = BLACK_PIECE
    board[4][3] = BLACK_PIECE
    board[4][4] = WHITE_PIECE
    return board

def on_board(x, y):
    return 0 <= x < ROWS and 0 <= y < COLS

def valid_moves(board, player):
    return [(x, y) for x in range(ROWS) for y in range(COLS)
            if board[x][y] == EMPTY and is_valid_move(board, player, x, y)]

def is_valid_move(board, player, x, y):
    opponent = WHITE_PIECE if player == BLACK_PIECE else BLACK_PIECE
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
    opponent = WHITE_PIECE if player == BLACK_PIECE else BLACK_PIECE
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
    while True:
        valid_list = valid_moves(current_board, current_player)
        draw_board(current_board, valid_list)
        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = pygame.mouse.get_pos()
                if my > BOARD_SIZE:
                    continue
                x, y = my // CELL_SIZE, mx // CELL_SIZE
                if (x, y) in valid_list:
                    make_move(current_board, current_player, x, y)
                    animate_piece(x, y, BLACK if current_player == BLACK_PIECE else WHITE)
                    current_player = WHITE_PIECE if current_player == BLACK_PIECE else BLACK_PIECE

                    if not valid_moves(current_board, current_player):
                        current_player = WHITE_PIECE if current_player == BLACK_PIECE else BLACK_PIECE
                        if not valid_moves(current_board, current_player):
                            draw_board(current_board, [])
                            pygame.display.flip()
                            show_winner(current_board)
                            return

if __name__ == "__main__":
    main()
