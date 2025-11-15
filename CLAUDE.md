# CLAUDE.md - プロジェクト開発メモ

このドキュメントは、Claude AIによるコード整理と、プロジェクトの技術的な詳細を記録したものです。

## プロジェクト概要

MCP9601熱電対温度センサーを使用した温度測定・記録システム。Arduino上でセンサーからデータを取得し、Pythonスクリプトを介してInfluxDBに保存します。

## アーキテクチャ

### ハードウェア層
```
[K型熱電対] --> [MCP9601] --I2C--> [Arduino]
                                      |
                         [7セグディスプレイ] (リアルタイム表示)
                         [Gas Sensor] (オプション)
```

### ソフトウェア層
```
[Arduino Sketch] --Serial(9600bps)--> [Python Script] --HTTP--> [InfluxDB]
                                            |
                                      [Data Buffer] (オフライン時)
```

## ファイル構成

### アクティブなファイル

#### Arduinoスケッチ
1. **MCP9601_7-seg.ino** - 基本版
   - 用途: 温度測定＋ディスプレイ表示
   - I2Cアドレス: MCP9601(0x67), Display(0x20)
   - 出力: 3フィールド（Th, Tc, ADC）

2. **MCP9601_box.ino** - 補正版
   - 用途: 温度測定＋0.7%補正
   - I2Cアドレス: MCP9601(0x67), Display(0x23)
   - 特記: ソフトウェアリセット機能
   - 出力: 3フィールド（補正後Th, Tc, ADC）

3. **MGSv2_MCP9601_WDT.ino** - 統合版
   - 用途: 温度測定＋ガスセンサー
   - I2Cアドレス: MCP9601(0x67), Display(0x20), Gas(0x08)
   - 特記: ウォッチドッグタイマー、Arduino Leonardo/Micro対応
   - 出力: 7フィールド（Th, Tc, ADC, NO2, C2H5OH, VOC, CO）

#### Pythonスクリプト
1. **mpx-x.py** - プロダクション版（推奨）
   - InfluxDB: v2 API
   - 特徴:
     - 包括的なエラーハンドリング
     - データバッファリング（最大1000件）
     - ネットワーク状態監視
     - DNS解決チェック
     - 自動再接続（シリアル/InfluxDB）
     - ログファイル出力
   - データ検証:
     - 温度範囲: -270〜800°C
     - ADC範囲: -5000〜33000μV
     - NaN検出
   - 測定値: mpc9601_measure (Th, Tc, T_ADC)

### アーカイブファイル（old/ディレクトリ）

1. **mgs_csv_r.py**
   - InfluxDB: v1 API
   - 用途: ガスセンサー統合版（旧）
   - 測定値:
     - mpc9601_measure (Th, Tc, ADC)
     - mgs_v2_measure_R (NO2, C2H5OH, VOC, CO)
   - 特記: シンプルなリトライ機能（@retry decorator）

2. **mpx-x_csv_inf_noretry.py**
   - InfluxDB: v1 API
   - 用途: 温度センサーのみ（旧）
   - 測定値: mpc9601_measure (Th, Tc, ADC)
   - 特記: リトライなし、最小実装

## 技術的な詳細

### MCP9601設定
- ADC解像度: 18ビット
- 熱電対タイプ: K型
- フィルター係数: 3
- アラート設定: Alert #1 @ 30°C（上昇）

### I2C通信

#### アドレスマッピング
| デバイス | アドレス | 用途 |
|---------|---------|------|
| MCP9601 | 0x67 | 温度センサー |
| 7セグディスプレイ | 0x20/0x23 | 温度表示 |
| Gas Sensor | 0x08 | ガス検出 |

#### 7セグディスプレイプロトコル
- 初期化: 'v' コマンド
- 明るさ: 0x7A (0-100%)
- 小数点: 0x77 (ビットマスク)
- データ: 4桁の温度値（0.1°C単位）

### シリアル通信

#### プロトコル
- ボーレート: 9600 bps
- フォーマット: CSV
- エンコーディング: UTF-8
- 改行: `\n`

#### 初期化シーケンス
Arduinoブート時に以下のメッセージを出力:
```
Adafruit MCP9601 test
Found MCP9601!
ADC resolution set to 18 bits
Thermocouple type set to K type
Filter coefficient value set to: 3
Alert #1 temperature set to 30
------------------------------
```

Pythonスクリプトはこれらを検出してフィルタリングします。

### データフロー

#### 正常時
```
Arduino -> Serial -> Python -> InfluxDB
         (CSV)            (JSON)
```

#### オフライン時
```
Arduino -> Serial -> Python -> Buffer (deque, max 1000)
                              |
                              v
                        (再接続時に送信)
```

### エラーハンドリング

#### シリアル通信
- 接続失敗: 最大3回リトライ（5秒間隔）
- 読み取りエラー: 連続10回でリセット
- タイムアウト: 2秒

#### InfluxDB通信
- 書き込み失敗: 最大3回リトライ（1秒間隔）
- 接続失敗: バッファに保存
- ネットワークチェック: 30秒間隔
- バッファフラッシュ: 60秒間隔（最大50件/回）

### データ検証

#### 範囲チェック
```python
TEMP_MIN = -270.0  # 絶対零度近く
TEMP_MAX = 800.0   # K型熱電対の上限
ADC_MIN = -5000.0  # マイクロボルト
ADC_MAX = 33000.0  # マイクロボルト
```

#### 検証項目
- フィールド数の確認
- 数値変換の可否
- 範囲内かどうか
- NaN検出

## 開発の変遷

### Phase 1: 基本実装
- MCP9601との通信確立
- 7セグディスプレイ表示
- シリアル出力

### Phase 2: データ記録
- InfluxDB v1統合
- CSV出力（廃止）
- 基本的なリトライ

### Phase 3: 信頼性向上
- InfluxDB v2移行
- 包括的なエラーハンドリング
- データバッファリング
- ネットワーク監視

### Phase 4: 機能拡張
- ガスセンサー統合
- ウォッチドッグタイマー
- 温度補正機能

## 既知の問題と制限事項

### Arduino
1. **MCP9601_box.ino**: ウォッチドッグタイマー機能がコメントアウト
   - 理由: 一部の環境で不安定
   - 対策: software_reset()内で無限ループ使用

2. **MGSv2_MCP9601_WDT.ino**: Arduino Leonardo/Micro専用
   - bootKeyPtr設定がLeonardo/Micro固有
   - 他のボードでは要調整

### Python
1. **mpx-x.py**: InfluxDB認証情報がハードコード
   - セキュリティリスク
   - 推奨: 環境変数化または設定ファイル化

2. バッファサイズ制限（1000件）
   - 長期間のオフラインには不十分
   - 推奨: ファイルベースの永続化

## 改善案

### セキュリティ
```python
# 環境変数化
import os
INFLUX_TOKEN = os.getenv('INFLUX_TOKEN')
INFLUX_URL = os.getenv('INFLUX_URL')
```

### 永続化
```python
# バッファの永続化
import pickle
def save_buffer(self):
    with open('buffer.pkl', 'wb') as f:
        pickle.dump(list(self.data_buffer), f)
```

### 設定ファイル化
```yaml
# config.yaml
serial:
  port: /dev/ttyACM0
  baud: 9600
influxdb:
  url: http://localhost:8086
  token: your-token
  org: your-org
  bucket: your-bucket
```

## 使用例

### ベーシックな温度測定
```bash
# Arduino: MCP9601_7-seg.ino
# Python: mpx-x.py
arduino-cli compile --fqbn arduino:avr:uno MCP9601_7-seg.ino
arduino-cli upload -p /dev/ttyACM0 --fqbn arduino:avr:uno MCP9601_7-seg.ino
python3 mpx-x.py
```

### ガスセンサー統合
```bash
# Arduino: MGSv2_MCP9601_WDT.ino
# Python: old/mgs_csv_r.py (または mpx-x.py with modification)
arduino-cli compile --fqbn arduino:avr:leonardo MGSv2_MCP9601_WDT.ino
arduino-cli upload -p /dev/ttyACM0 --fqbn arduino:avr:leonardo MGSv2_MCP9601_WDT.ino
python3 old/mgs_csv_r.py
```

## 参考資料

### データシート
- [MCP9600/9601 Datasheet](https://ww1.microchip.com/downloads/en/DeviceDoc/MCP960X-Data-Sheet-20005426.pdf)
- [Adafruit MCP9601 Guide](https://learn.adafruit.com/adafruit-mcp9601-i2c-thermocouple-amplifier)

### ライブラリ
- [Adafruit_MCP9601](https://github.com/adafruit/Adafruit_MCP9601)
- [influxdb-client-python](https://github.com/influxdata/influxdb-client-python)

## 変更履歴

### 2025-11-15
- 古いPythonスクリプトを`old/`ディレクトリに移動
- README.md作成
- CLAUDE.md作成（このドキュメント）

### 過去のコミット（gitログより）
- 04227bc: mpx-x.py パラメータ更新
- b9382ba: mpx-x.py 更新
- 6818d5b: mpx-x.py 作成
- 682c8fa: MCP9601_box.ino 更新
- 77a50d7: 補正値導入（+4.5°C/100°C）

## メンテナンス

### 定期的なチェック項目
- [ ] センサーのキャリブレーション
- [ ] InfluxDBのディスク使用量
- [ ] ログファイルのローテーション
- [ ] Arduinoライブラリの更新
- [ ] Pythonパッケージの更新

### バックアップ
```bash
# InfluxDBバックアップ
influx backup /path/to/backup

# 設定ファイルバックアップ
cp mpx-x.py mpx-x.py.bak
```

## ライセンス

MITライセンス - 詳細は[LICENSE](LICENSE)を参照。

---

*このドキュメントはClaude AIにより2025年11月15日に生成されました。*
