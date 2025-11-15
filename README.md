# MCP9601 I2C Arduino

MCP9601熱電対温度センサーとArduinoを使った温度測定システムです。複数のバリエーションとPythonスクリプトを提供しています。

## 概要

このプロジェクトは、Adafruit MCP9601熱電対アンプを使用して、K型熱電対から温度データを読み取り、以下の機能を提供します：

- シリアル通信による温度データ出力
- 7セグメントディスプレイへの温度表示
- InfluxDBへのデータ保存
- オプション：ガスセンサー（Multichannel Gas Sensor）との統合

## 必要なハードウェア

- Arduino（Leonardo、Uno等）
- Adafruit MCP9601熱電対アンプ（I2Cアドレス: 0x67）
- K型熱電対
- 7セグメントディスプレイ（OpenSegment、I2Cアドレス: 0x20 or 0x23）
- （オプション）Seeed Multichannel Gas Sensor（I2Cアドレス: 0x08）

## 必要なライブラリ

### Arduino
- Adafruit_MCP9601
- Wire（標準ライブラリ）
- avr/wdt（ウォッチドッグタイマー使用時）
- Multichannel_Gas_GMXXX（ガスセンサー使用時）

### Python
- pyserial
- influxdb-client
- logging（標準ライブラリ）

## Arduinoスケッチ

### 1. MCP9601_7-seg.ino
基本的な温度測定＋7セグメントディスプレイ表示

**特徴：**
- MCP9601から温度データ読み取り（熱電対温度、周囲温度、ADC値）
- 7セグメントディスプレイに温度表示（点滅機能付き）
- シリアル出力（CSV形式）

**I2Cアドレス：**
- MCP9601: 0x67
- 7セグディスプレイ: 0x20

**出力フォーマット：**
```
[熱電対温度],[周囲温度],[ADC値×2]
```

### 2. MCP9601_box.ino
温度補正機能付きバージョン

**特徴：**
- 温度補正：測定値から0.7%を減算
- ソフトウェアリセット機能（無限ループ方式）
- ブライトネス調整（100%）

**I2Cアドレス：**
- MCP9601: 0x67
- 7セグディスプレイ: 0x23

**補正式：**
```cpp
readThermocouple() - readThermocouple() * (0.7 / 100)
```

### 3. MGSv2_MCP9601_WDT.ino
ガスセンサー統合版（最も高機能）

**特徴：**
- MCP9601温度センサー
- Multichannel Gas Sensor（NO2、C2H5OH、VOC、CO）
- ウォッチドッグタイマー機能
- 7セグメントディスプレイ表示

**I2Cアドレス：**
- MCP9601: 0x67
- ガスセンサー: 0x08
- 7セグディスプレイ: 0x20

**出力フォーマット：**
```
[熱電対温度],[周囲温度],[ADC値×2],[NO2],[C2H5OH],[VOC],[CO]
```

## Pythonスクリプト

### mpx-x.py（推奨）
最新の機能豊富なInfluxDB v2対応スクリプト

**特徴：**
- InfluxDB v2 API対応
- エラーハンドリングとリトライ機能
- オフライン時のデータバッファリング（最大1000件）
- ネットワーク状態監視とDNSチェック
- ロギング機能（ファイル＋コンソール）
- センサーデータの妥当性検証

**設定項目：**
```python
SERIAL_PORT = '/dev/ttyACM0'
SERIAL_BAUD = 9600
INFLUX_BUCKET = "your-bucket"
INFLUX_TOKEN = "your-token"
INFLUX_ORG = "your-org"
INFLUX_URL = "http://your-server:8086"
```

**機能：**
- 自動再接続（シリアル＆InfluxDB）
- データバッファ（ネットワーク障害時）
- 温度範囲検証（-270〜800°C）
- 初期化メッセージフィルタリング

### old/以下のスクリプト（参考用）

#### mgs_csv_r.py
- InfluxDB v1対応
- ガスセンサー7フィールド対応
- シンプルなリトライ機能

#### mpx-x_csv_inf_noretry.py
- InfluxDB v1対応
- 温度センサー3フィールドのみ
- リトライなし

## 使用方法

### Arduinoスケッチのアップロード

1. Arduino IDEで必要なライブラリをインストール
2. 使用するスケッチを開く
3. ボードとポートを選択
4. アップロード

### Pythonスクリプトの実行

```bash
# 必要なパッケージをインストール
pip install pyserial influxdb-client

# スクリプトを実行
python3 mpx-x.py
```

## データフロー

```
[MCP9601] --I2C--> [Arduino] --Serial--> [Python] --HTTP--> [InfluxDB]
    |
    +---> [7セグディスプレイ]（リアルタイム表示）
```

## トラブルシューティング

### センサーが見つからない
- I2Cアドレスを確認（デフォルト: 0x67）
- 配線を確認（SDA、SCL、VCC、GND）
- I2Cスキャナーで確認

### シリアル接続エラー
- ポート名を確認（`/dev/ttyACM0`、`/dev/ttyUSB0`等）
- ポートのパーミッション確認: `sudo chmod 666 /dev/ttyACM0`
- デバイスマネージャーでポート確認（Windows）

### InfluxDB接続エラー
- URL、トークン、組織名、バケット名を確認
- ネットワーク接続を確認
- InfluxDBサーバーが起動しているか確認
- DNS解決を確認

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。詳細は[LICENSE](LICENSE)ファイルを参照してください。

## 貢献

プルリクエストや問題報告を歓迎します。

## 関連リンク

- [Adafruit MCP9601](https://www.adafruit.com/product/4101)
- [InfluxDB](https://www.influxdata.com/)
- [Arduino](https://www.arduino.cc/)
