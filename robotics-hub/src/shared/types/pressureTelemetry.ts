/** Pico W → pressure_telemetry_server → Hub の圧力サンプル */

/** DF9-40@2kg のフルスケール（センサ 1 本）[kg] */
export const DF9_FORCE_MAX_KG = 2;

export type PressureTelemetryHelloPayload = {
  ok: boolean;
  server_ts: number;
  sample_count?: number;
  stale_sec?: number | null;
};

/** 足裏 1 隅の計測値（未設置コーナーは null） */
export type PressureCornerSample = {
  /** 力 [kg]（DF9-40@2kg 換算） */
  force_kg: number;
  /** フルスケール比 [%]（0–100、センサ単体） */
  force_pct?: number;
  /** 分圧電圧 [V] */
  voltage_v?: number;
  /** センサー抵抗 [Ω] */
  rs_ohm?: number;
  /** ADS1115 チャネル番号（0=A0 …） */
  channel?: number;
};

/** 足裏フレーム四隅（上面・つま先が上） */
export type PressureFootCorners = {
  /** 左上 ← ADS1115 A0 */
  top_left: PressureCornerSample | null;
  /** 右上 ← ADS1115 A1 */
  top_right: PressureCornerSample | null;
  /** 右下 ← ADS1115 A2 */
  bottom_right: PressureCornerSample | null;
  /** 左下 ← ADS1115 A3 */
  bottom_left: PressureCornerSample | null;
};

export type PressureTelemetrySample = {
  /**
   * 合計力 [kg]。
   * 四隅ペイロードでは設置センサの合計。レガシー単センサではその 1 点。
   */
  force_kg: number;
  /** ブリッジ受信時刻（Unix 秒） */
  server_ts: number;
  /** 分圧電圧 [V]（レガシー単センサ） */
  voltage_v?: number;
  /** センサー抵抗 [Ω]（レガシー単センサ） */
  rs_ohm?: number;
  /** フルスケール比 [%]（0–100） */
  force_pct?: number;
  /** ADC ピン番号（レガシー・オンボード ADC 時代） */
  adc_pin?: number;
  /** Pico 側の相対時刻（任意） */
  device_ts?: number;
  /** Pico 側連番 */
  seq?: number;
  /** センサー識別子 */
  sensor_id?: string;
  /** 足裏四隅（新フォーマット）。無い場合はレガシー単点表示にフォールバック */
  corners?: PressureFootCorners;
};
