import pygame
import sys

# 定数定義
WIDTH, HEIGHT = 640, 640
ROWS, COLS = 8, 8
CELL_SIZE = WIDTH // COLS
GREEN = (0, 128, 0)
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
BG_COLOR = GREEN

EMPTY = 0
BLACK_PIECE = 1
WHITE_PIECE = 2

# 方向
DIRECTIONS = [(-1, -1), (-1, 0), (-1, 1),
              (0, -1),          (0, 1),
              (1, -1),  (1, 0), (1, 1)]

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("オセロ")

# ボード初期化
def init_board():
    board = [[EMPTY for _ in range(COLS)] for _ in range(ROWS)]
    board[3][3] = WHITE_PIECE
    board[3][4] = BLACK_PIECE
    board[4][3] = BLACK_PIECE
    board[4][4] = WHITE_PIECE
    return board

def draw_board(board):
    screen.fill(BG_COLOR)
    for x in range(ROWS):
        for y in range(COLS):
            rect = pygame.Rect(y*CELL_SIZE, x*CELL_SIZE, CELL_SIZE, CELL_SIZE)
            pygame.draw.rect(screen, BLACK, rect, 1)
            if board[x][y] == BLACK_PIECE:
                pygame.draw.circle(screen, BLACK, rect.center, CELL_SIZE//2 - 5)
            elif board[x][y] == WHITE_PIECE:
                pygame.draw.circle(screen, WHITE, rect.center, CELL_SIZE//2 - 5)

def on_board(x, y):
    return 0 <= x < ROWS and 0 <= y < COLS

def valid_moves(board, player):
    moves = []
    for x in range(ROWS):
        for y in range(COLS):
            if board[x][y] == EMPTY and is_valid_move(board, player, x, y):
                moves.append((x, y))
    return moves

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
        stones_to_flip = []
        while on_board(nx, ny) and board[nx][ny] == opponent:
            stones_to_flip.append((nx, ny))
            nx += dx
            ny += dy
        if on_board(nx, ny) and board[nx][ny] == player:
            for fx, fy in stones_to_flip:
                board[fx][fy] = player
    return True

def count_stones(board):
    black = sum(row.count(BLACK_PIECE) for row in board)
    white = sum(row.count(WHITE_PIECE) for row in board)
    return black, white

def show_winner(board):
    black, white = count_stones(board)
    font = pygame.font.SysFont(None, 48)
    if black > white:
        text = font.render("黒の勝ち！", True, BLACK)
    elif white > black:
        text = font.render("白の勝ち！", True, WHITE)
    else:
        text = font.render("引き分け！", True, (255, 255, 0))
    screen.blit(text, (WIDTH // 2 - text.get_width() // 2, HEIGHT // 2 - text.get_height() // 2))
    pygame.display.flip()
    pygame.time.wait(3000)

def main():
    board = init_board()
    current_player = BLACK_PIECE

    while True:
        draw_board(board)
        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = pygame.mouse.get_pos()
                x, y = my // CELL_SIZE, mx // CELL_SIZE
                if make_move(board, current_player, x, y):
                    current_player = WHITE_PIECE if current_player == BLACK_PIECE else BLACK_PIECE

                    # 両者パス判定
                    if not valid_moves(board, current_player):
                        current_player = WHITE_PIECE if current_player == BLACK_PIECE else BLACK_PIECE
                        if not valid_moves(board, current_player):
                            show_winner(board)
                            return

if __name__ == "__main__":
    main()
