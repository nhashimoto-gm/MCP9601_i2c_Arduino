import serial
import time
import logging
from datetime import datetime
from collections import deque
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.rest import ApiException
import socket

# ロギング設定
logging.basicConfig(
    level=logging.INFO, # logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('sensor_log.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 設定
SERIAL_PORT = '/dev/ttyACM0'
SERIAL_BAUD = 9600
SERIAL_TIMEOUT = 2
SERIAL_RETRY_INTERVAL = 5
SERIAL_MAX_RETRIES = 3

INFLUX_BUCKET = "xxxxxx"
INFLUX_TOKEN = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
INFLUX_ORG = "xxxx.org"
INFLUX_URL = "http://www.xxxxxxxxxx.xxx:8086"
INFLUX_TIMEOUT = 10000  # ミリ秒

# データ検証範囲（フィールドごと）
TEMP_MIN = -270.0
TEMP_MAX = 800.0
ADC_MIN = -5000.0
ADC_MAX = 33000.0

READ_INTERVAL = 0.5  # 秒

# バッファ設定
MAX_BUFFER_SIZE = 1000  # 最大バッファサイズ
NETWORK_CHECK_INTERVAL = 30  # ネットワークチェック間隔（秒）

# 初期化メッセージのパターン
INIT_MESSAGE_PATTERNS = [
    'Adafruit',
    'Found MCP',
    'ADC resolution',
    'Thermocouple',
    'Filter coefficient',
    'Alert',
    '---'
]


class NetworkChecker:
    """ネットワーク接続状態をチェックするクラス"""
    
    @staticmethod
    def check_dns(hostname):
        """DNS解決をチェック"""
        try:
            # URLからホスト名を抽出
            if '://' in hostname:
                hostname = hostname.split('://')[1].split(':')[0].split('/')[0]
            
            socket.gethostbyname(hostname)
            return True
        except socket.gaierror:
            return False
    
    @staticmethod
    def check_connection(url, timeout=5):
        """接続をチェック"""
        try:
            hostname = url.split('://')[1].split(':')[0]
            port = int(url.split(':')[-1].split('/')[0]) if ':' in url.split('://')[1] else 80
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((hostname, port))
            sock.close()
            return result == 0
        except Exception:
            return False


class SerialReader:
    """シリアル接続を管理するクラス"""
    
    def __init__(self, port, baudrate, timeout):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None
        self.init_phase = True
        self.init_lines_count = 0
    
    def connect(self, max_retries=SERIAL_MAX_RETRIES):
        """シリアルポートに接続（リトライ機能付き）"""
        for attempt in range(max_retries):
            try:
                self.ser = serial.Serial(
                    self.port,
                    self.baudrate,
                    timeout=self.timeout,
                    write_timeout=self.timeout
                )
                self.ser.flush()
                time.sleep(0.5)
                logger.info(f"シリアルポート接続成功: {self.port}")
                self.init_phase = True
                self.init_lines_count = 0
                return True
            except serial.SerialException as e:
                logger.warning(f"接続試行 {attempt + 1}/{max_retries} 失敗: {e}")
                time.sleep(SERIAL_RETRY_INTERVAL)
        
        logger.error(f"シリアルポート接続失敗: {self.port}")
        return False
    
    def reconnect(self):
        """再接続"""
        logger.info("シリアルポート再接続試行中...")
        self.close()
        time.sleep(2)
        return self.connect()
    
    def read_line(self):
        """1行読み取り（エラーハンドリング付き）"""
        if not self.ser or not self.ser.is_open:
            raise serial.SerialException("シリアルポートが開いていません")
        
        try:
            if self.ser.in_waiting > 0:
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                return line
        except (serial.SerialException, UnicodeDecodeError) as e:
            logger.error(f"データ読み取りエラー: {e}")
            raise
        
        return None
    
    def is_init_message(self, line):
        """初期化メッセージかどうか判定"""
        if not line:
            return False
        
        for pattern in INIT_MESSAGE_PATTERNS:
            if pattern in line:
                return True
        
        if self.init_phase and self.init_lines_count < 10:
            parts = line.split(',')
            if len(parts) != 3:
                return True
            try:
                [float(p) for p in parts]
                self.init_phase = False
            except ValueError:
                return True
        
        return False
    
    def close(self):
        """接続を閉じる"""
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
                logger.info("シリアルポートを閉じました")
            except Exception as e:
                logger.error(f"シリアルポートのクローズエラー: {e}")


class InfluxDBWriter:
    """InfluxDB書き込みを管理するクラス"""
    
    def __init__(self, url, token, org, bucket):
        self.url = url
        self.token = token
        self.org = org
        self.bucket = bucket
        self.client = None
        self.write_api = None
        self.is_connected = False
        self.last_network_check = 0
        self.data_buffer = deque(maxlen=MAX_BUFFER_SIZE)  # データバッファ
        self.consecutive_failures = 0
        self.network_checker = NetworkChecker()
    
    def connect(self):
        """InfluxDBに接続"""
        try:
            # DNS解決チェック
            if not self.network_checker.check_dns(self.url):
                logger.error("DNS解決失敗: InfluxDBサーバーのホスト名を解決できません")
                return False
            
            self.client = InfluxDBClient(
                url=self.url,
                token=self.token,
                org=self.org,
                timeout=INFLUX_TIMEOUT
            )
            self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
            
            # 接続テスト
            self.client.ping()
            logger.info("InfluxDB接続成功")
            self.is_connected = True
            self.consecutive_failures = 0
            return True
        except Exception as e:
            logger.error(f"InfluxDB接続エラー: {e}")
            self.is_connected = False
            return False
    
    def check_and_reconnect(self):
        """接続状態をチェックして必要なら再接続"""
        current_time = time.time()
        
        # 定期的なネットワークチェック
        if current_time - self.last_network_check > NETWORK_CHECK_INTERVAL:
            self.last_network_check = current_time
            
            # DNS解決チェック
            if not self.network_checker.check_dns(self.url):
                logger.warning("DNS解決失敗: ネットワーク接続を確認してください")
                self.is_connected = False
                return False
            
            # 接続チェック
            if not self.is_connected:
                logger.info("InfluxDB再接続を試行します...")
                if self.connect():
                    logger.info("再接続成功")
                    return True
                else:
                    logger.warning("再接続失敗")
                    return False
        
        return self.is_connected
    
    def write_data(self, data, max_retries=3):
        """データ書き込み（リトライ機能付き）"""
        if not self.is_connected:
            # バッファに保存
            self.data_buffer.append(data[0])
            logger.debug(f"オフライン: データをバッファに保存 (バッファサイズ: {len(self.data_buffer)})")
            return False
        
        for attempt in range(max_retries):
            try:
                self.write_api.write(self.bucket, self.org, data)
                logger.debug("データ書き込み成功")
                self.consecutive_failures = 0
                return True
            except ApiException as e:
                logger.warning(f"書き込み試行 {attempt + 1}/{max_retries} 失敗: {e}")
                time.sleep(1)
            except (socket.gaierror, socket.error, ConnectionError) as e:
                logger.error(f"ネットワークエラー: {e}")
                self.is_connected = False
                self.consecutive_failures += 1
                # バッファに保存
                self.data_buffer.append(data[0])
                logger.info(f"データをバッファに保存 (バッファサイズ: {len(self.data_buffer)})")
                return False
            except Exception as e:
                logger.error(f"予期しない書き込みエラー: {e}")
                self.consecutive_failures += 1
                break
        
        # 失敗時はバッファに保存
        self.data_buffer.append(data[0])
        logger.warning(f"書き込み失敗: バッファに保存 (バッファサイズ: {len(self.data_buffer)})")
        return False
    
    def flush_buffer(self):
        """バッファに溜まったデータを書き込み"""
        if not self.data_buffer or not self.is_connected:
            return 0
        
        success_count = 0
        batch_size = min(50, len(self.data_buffer))  # 一度に50件まで
        
        logger.info(f"バッファフラッシュ開始: {len(self.data_buffer)}件")
        
        while self.data_buffer and success_count < batch_size:
            data = self.data_buffer[0]  # 先頭を取得（まだ削除しない）
            
            try:
                self.write_api.write(self.bucket, self.org, [data])
                self.data_buffer.popleft()  # 成功したら削除
                success_count += 1
            except Exception as e:
                logger.error(f"バッファフラッシュエラー: {e}")
                self.is_connected = False
                break
        
        if success_count > 0:
            logger.info(f"バッファフラッシュ完了: {success_count}件送信、残り{len(self.data_buffer)}件")
        
        return success_count
    
    def close(self):
        """接続を閉じる"""
        # バッファに残っているデータを保存
        if self.data_buffer:
            logger.warning(f"未送信データ {len(self.data_buffer)}件が残っています")
            # 必要ならファイルに保存する処理を追加
        
        if self.client:
            try:
                self.client.close()
                logger.info("InfluxDB接続を閉じました")
            except Exception as e:
                logger.error(f"InfluxDB切断エラー: {e}")


def validate_data(data_list):
    """データの妥当性検証"""
    if len(data_list) < 3:
        return False, "データ数不足"
    
    try:
        th = float(data_list[0])
        tc = float(data_list[1])
        t_adc = float(data_list[2])
        
        if not (TEMP_MIN <= th <= TEMP_MAX):
            return False, f"Th値が範囲外: {th}"
        if not (TEMP_MIN <= tc <= TEMP_MAX):
            return False, f"Tc値が範囲外: {tc}"
        if not (ADC_MIN <= t_adc <= ADC_MAX):
            return False, f"T_ADC値が範囲外: {t_adc}"
        
        if any(val != val for val in [th, tc, t_adc]):
            return False, "NaN値を検出"
        
        return True, (th, tc, t_adc)
    except (ValueError, TypeError) as e:
        return False, f"数値変換エラー: {e}"


def parse_sensor_data(line):
    """センサーデータをパース"""
    if not line or line.strip() == '':
        return None
    
    data_parts = line.split(',')
    is_valid, result = validate_data(data_parts)
    
    if not is_valid:
        logger.warning(f"無効なデータ: {line} - 理由: {result}")
        return None
    
    th, tc, t_adc = result
    logger.info(f'Th: {th:.2f}°C, Tc: {tc:.2f}°C, T_ADC: {t_adc:.2f}')
    
    return {
        "measurement": "mpc9601_measure",
        "fields": {
            "Th(degC)": th,
            "Tc(degC)": tc,
            "T_ADC": t_adc
        },
        "time": datetime.utcnow().isoformat() + "Z"
    }


def run():
    """メイン処理"""
    logger.info("プログラム開始")
    
    # 初期化
    serial_reader = SerialReader(SERIAL_PORT, SERIAL_BAUD, SERIAL_TIMEOUT)
    influx_writer = InfluxDBWriter(INFLUX_URL, INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET)
    
    # 接続
    if not serial_reader.connect():
        logger.error("シリアルポート接続失敗。終了します。")
        return
    
    if not influx_writer.connect():
        logger.warning("InfluxDB接続失敗。オフラインモードで開始します。")
    
    # メインループ
    consecutive_errors = 0
    max_consecutive_errors = 10
    last_buffer_flush = time.time()
    buffer_flush_interval = 60  # バッファフラッシュ間隔（秒）
    
    try:
        while True:
            try:
                # 定期的にInfluxDB接続をチェック
                influx_writer.check_and_reconnect()
                
                # 定期的にバッファをフラッシュ
                if time.time() - last_buffer_flush > buffer_flush_interval:
                    if influx_writer.is_connected and influx_writer.data_buffer:
                        influx_writer.flush_buffer()
                    last_buffer_flush = time.time()
                
                # データ読み取り
                line = serial_reader.read_line()
                
                if line is None:
                    time.sleep(READ_INTERVAL)
                    continue
                
                # 初期化メッセージの場合はそのまま出力
                if serial_reader.is_init_message(line):
                    print(line)
                    logger.info(f"初期化メッセージ: {line}")
                    serial_reader.init_lines_count += 1
                    time.sleep(READ_INTERVAL)
                    continue
                
                # データパース
                sensor_data = parse_sensor_data(line)
                
                if sensor_data is None:
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error(f"連続エラー {max_consecutive_errors} 回。再接続試行。")
                        if not serial_reader.reconnect():
                            logger.error("再接続失敗。終了します。")
                            break
                        consecutive_errors = 0
                    time.sleep(READ_INTERVAL)
                    continue
                
                # InfluxDBに書き込み
                if influx_writer.write_data([sensor_data]):
                    consecutive_errors = 0
                # 書き込み失敗時はバッファに保存済み
                
                time.sleep(READ_INTERVAL)
                
            except serial.SerialException as e:
                logger.error(f"シリアル通信エラー: {e}")
                consecutive_errors += 1
                
                if consecutive_errors >= 3:
                    if not serial_reader.reconnect():
                        logger.error("再接続失敗。終了します。")
                        break
                    consecutive_errors = 0
                
                time.sleep(2)
            
            except Exception as e:
                logger.error(f"予期しないエラー: {e}", exc_info=True)
                consecutive_errors += 1
                time.sleep(2)
    
    except KeyboardInterrupt:
        logger.info("ユーザーによる中断")
    
    finally:
        # 最後のバッファフラッシュ試行
        if influx_writer.data_buffer:
            logger.info("終了前にバッファをフラッシュします...")
            if influx_writer.is_connected:
                influx_writer.flush_buffer()
        
        # クリーンアップ
        serial_reader.close()
        influx_writer.close()
        logger.info("プログラム終了")


if __name__ == '__main__':
    run()
