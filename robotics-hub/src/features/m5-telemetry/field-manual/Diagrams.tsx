/**
 * 手帳の章頭に置く模式図。Markdown では書きにくい「切れ目」を色面で示す。
 */

/** USB フレームのバイト列を帯にする。 */
export function UsbFrameStrip() {
  const parts = [
    { label: "AA 55", hint: "同期", flex: 1.1, tone: "sync" },
    { label: "type", hint: "種類", flex: 0.9, tone: "type" },
    { label: "len16", hint: "LE", flex: 1.0, tone: "len" },
    { label: "payload", hint: "最大 512 B", flex: 3.2, tone: "pay" },
    { label: "CRC16", hint: "type〜末尾", flex: 1.1, tone: "crc" },
  ] as const;
  return (
    <figure className="m5-manual__figure">
      <div className="m5-manual__strip" aria-hidden="true">
        {parts.map((p) => (
          <div key={p.label} className={"m5-manual__strip-cell m5-manual__strip-cell--" + p.tone} style={{ flex: p.flex }}>
            <span className="m5-manual__strip-label">{p.label}</span>
            <span className="m5-manual__strip-hint">{p.hint}</span>
          </div>
        ))}
      </div>
      <figcaption>1 フレーム。マジックは CRC に入れない。テレメトリ payload は 316 バイト。</figcaption>
    </figure>
  );
}

/** 8 MB フラッシュの切れ目（Arduino 既定の模式。専用 partitions.csv はない）。 */
export function FlashMap() {
  const bands = [
    { id: "bl", label: "boot", hint: "0x0", flex: 0.55, tone: "dim" },
    { id: "pt", label: "table", hint: "0x8000", flex: 0.45, tone: "dim" },
    { id: "nvs", label: "NVS", hint: "0x9000", flex: 0.9, tone: "nvs" },
    { id: "ota", label: "otadata", hint: "0xE000", flex: 0.5, tone: "dim" },
    { id: "app", label: "app · rt-usb", hint: "0x10000", flex: 4.2, tone: "app" },
    { id: "rest", label: "余り", hint: "〜 8 MB", flex: 2.2, tone: "rest" },
  ] as const;
  return (
    <figure className="m5-manual__figure">
      <div className="m5-manual__strip m5-manual__strip--flash" aria-hidden="true">
        {bands.map((b) => (
          <div key={b.id} className={"m5-manual__strip-cell m5-manual__strip-cell--" + b.tone} style={{ flex: b.flex }}>
            <span className="m5-manual__strip-label">{b.label}</span>
            <span className="m5-manual__strip-hint">{b.hint}</span>
          </div>
        ))}
      </div>
      <figcaption>
        書き込みは app。校正と関節経路は NVS。幅は模式で、バイト数の正本ではない。
      </figcaption>
    </figure>
  );
}

/** ブラウザ → ブリッジ → USB → I2C の層。 */
export function StackStrip() {
  const layers = [
    { id: "hub", title: "Hub", sub: "ブラウザ :5173" },
    { id: "pc", title: "lab_debug.py", sub: "Socket.IO :8794" },
    { id: "usb", title: "USB CDC", sub: "ver=10 バイナリ" },
    { id: "atom", title: "ATOM", sub: "Core1 20 Hz / Core0 USB" },
    { id: "i2c", title: "Grove I2C", sub: "PaHub · 8Servos · 足" },
  ] as const;
  return (
    <figure className="m5-manual__figure">
      <ol className="m5-manual__stack">
        {layers.map((l, i) => (
          <li key={l.id} className={"m5-manual__stack-item m5-manual__stack-item--" + l.id}>
            <span className="m5-manual__stack-idx">{String(i).padStart(2, "0")}</span>
            <span className="m5-manual__stack-title">{l.title}</span>
            <span className="m5-manual__stack-sub">{l.sub}</span>
          </li>
        ))}
      </ol>
      <figcaption>下へ行くほど金属に近い。JSON の op は 8794 で止まり、ATOM にはバイナリだけが届く。</figcaption>
    </figure>
  );
}

/** 双コアの役割。 */
export function DualCore() {
  return (
    <figure className="m5-manual__figure">
      <div className="m5-manual__cores">
        <div className="m5-manual__core">
          <div className="m5-manual__core-id">Core 1</div>
          <div className="m5-manual__core-job">制御 20 Hz</div>
          <p>I2C · PWM · Snapshot を書く</p>
        </div>
        <div className="m5-manual__core m5-manual__core--usb">
          <div className="m5-manual__core-id">Core 0</div>
          <div className="m5-manual__core-job">USB</div>
          <p>コピーして送る。I2C は触らない</p>
        </div>
      </div>
      <figcaption>SCAN は Core 1 が I2C を使うので、その周期だけ伸びる。</figcaption>
    </figure>
  );
}

export type ManualDiagramId = "stack" | "flash" | "cores" | "usb";

export function ManualDiagram({ id }: { id: ManualDiagramId }) {
  if (id === "stack") return <StackStrip />;
  if (id === "flash") return <FlashMap />;
  if (id === "cores") return <DualCore />;
  return <UsbFrameStrip />;
}
