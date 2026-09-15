import numpy as np
import matplotlib.pyplot as plt

# --- 部屋設定 ---
room_width = 6  # m
room_height = 3  # m
resolution = 0.1
nx = int(room_width / resolution)
ny = int(room_height / resolution)
dx = dy = resolution
dt = 30  # 秒
alpha = 1.9e-5

T = np.full((ny, nx), 30.0)

# エアコン中央
ac_x = 0
ac_y = ny // 2

cooling_angle_deg = 30
cooling_radius_cells = 15  # 拡大（15セル = 1.5m）

# 壁近傍の拡散抑制
diffusion_map = np.full((ny, nx), alpha)
margin = 3
diffusion_map[:margin, :] *= 0.3
diffusion_map[-margin:, :] *= 0.3
diffusion_map[:, :margin] *= 0.3
diffusion_map[:, -margin:] *= 0.3

# --- 強化版ベクトル場（風速10m/sに相当） ---
U = np.zeros((ny, nx))
V = np.zeros((ny, nx))
for r in range(1, cooling_radius_cells + 1):
    for angle_deg in range(-cooling_angle_deg // 2, cooling_angle_deg // 2 + 1):
        angle_rad = np.radians(angle_deg)
        dx_ = int(round(r * np.cos(angle_rad)))
        dy_ = int(round(r * np.sin(angle_rad)))
        x = ac_x + dx_
        y = ac_y + dy_
        if 0 <= x < nx and 0 <= y < ny:
            U[y, x] = np.cos(angle_rad) * 10.0
            V[y, x] = np.sin(angle_rad) * 10.0

# --- 冷却処理（強化） ---
def apply_cooling(T):
    for r in range(1, cooling_radius_cells + 1):
        for angle_deg in range(-cooling_angle_deg // 2, cooling_angle_deg // 2 + 1):
            angle_rad = np.radians(angle_deg)
            dx_ = int(round(r * np.cos(angle_rad)))
            dy_ = int(round(r * np.sin(angle_rad)))
            x = ac_x + dx_
            y = ac_y + dy_
            if 0 <= x < nx and 0 <= y < ny:
                T[y, x] -= 5.0  # 冷却力を大幅アップ（1000kW相当）
    return T

# --- 拡散処理 ---
def diffuse_with_convection(T, alpha_map):
    T_new = T.copy()
    convection_bias = 0.05
    for y in range(1, ny - 1):
        for x in range(1, nx - 1):
            a = alpha_map[y, x]
            dTdx2 = (T[y, x + 1] - 2 * T[y, x] + T[y, x - 1]) / dx**2
            dTdy2 = (T[y + 1, x] - 2 * T[y, x] + T[y - 1, x]) / dy**2
            dTdy2 += convection_bias * (T[y + 1, x] - T[y, x]) / dy
            T_new[y, x] = T[y, x] + a * dt * (dTdx2 + dTdy2)
    return T_new

# --- 可視化初期化 ---
fig, ax = plt.subplots(figsize=(8, 5))
img = ax.imshow(T, cmap='coolwarm', vmin=10, vmax=32, origin='lower',
                extent=[0, room_width, 0, room_height])
X, Y = np.meshgrid(np.linspace(0, room_width, nx),
                   np.linspace(0, room_height, ny))
quiver = ax.quiver(X, Y, U, V, color='black', angles='xy', scale=50)
fig.colorbar(img, label='Temperature (°C)')

plt.xlabel("Width (m)")
plt.ylabel("Height (m)")
plt.title("Room Temp with High-Power AC (1000kW, 10m/s)")

# --- ループ：最高温度が20℃以下になるまで ---
time_elapsed = 0
while T.max() > 20.0:
    T = diffuse_with_convection(T, diffusion_map)
    T = apply_cooling(T)
    T = np.clip(T, 10.0, 100.0)

    time_elapsed += dt
    img.set_array(T)
    ax.set_title(f"Time: {time_elapsed // 60:.1f} min, Max Temp: {T.max():.2f}°C")
    plt.pause(0.01)

plt.show()
