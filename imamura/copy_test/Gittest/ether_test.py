from scapy.all import Ether, IP, TCP, sendp, hexdump

def simulate_ethernet_frame():
    # 1. Ethernetヘッダの作成 (レイヤー2)
    # dst: 宛先MACアドレス (ブロードキャスト)
    # src: 送信元MACアドレス (適当なダミー)
    eth_layer = Ether(dst="ff:ff:ff:ff:ff:ff", src="00:11:22:33:44:55")

    # 2. IPヘッダとTCPヘッダの作成 (レイヤー3, 4) - ペイロードとして載せる
    ip_layer = IP(src="192.168.1.100", dst="192.168.1.255")
    tcp_layer = TCP(sport=12345, dport=80)
    
    # 3. データの作成
    payload = "Hello Ethernet Simulation!"

    # 4. 全体を結合してパケットにする ("/" 演算子でスタックできます)
    packet = eth_layer / ip_layer / tcp_layer / payload

    print("--- 作成されたパケットの構造 ---")
    packet.show()

    print("\n--- バイナリダンプ (実際にケーブルを流れるデータ) ---")
    hexdump(packet)

    # 5. 送信 (実際にNICから送信する場合は sudo が必要)
    # sendp(packet, iface="eth0") 
    # ※実際に飛ばすとネットワーク管理者に怒られる可能性があるのでコメントアウトしています

if __name__ == "__main__":
    simulate_ethernet_frame()