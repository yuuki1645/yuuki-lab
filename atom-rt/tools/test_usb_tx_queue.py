"""USB 送信待ちが、関節指令の古い角度を捨てることを確認する。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# tools/ をパスに入れる。lab_debug.py と同じ `import lib...` になる。
_TOOLS = Path(__file__).resolve().parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from lib import rt_usb_proto as proto  # noqa: E402
from lib.lab_usb import _UsbTxQueue, _joint_channel  # noqa: E402


class UsbTxQueueTest(unittest.TestCase):
    def test_same_joint_keeps_only_the_latest_angle(self) -> None:
        """同じ軸を何度積んでも、出ていくのは最後の角度 1 本。"""
        tx = _UsbTxQueue()
        tx.put(proto.cmd_joint(3, 10.0))
        tx.put(proto.cmd_joint(3, 40.0))
        tx.put(proto.cmd_joint(3, 90.0))
        self.assertEqual(tx.drain(), [proto.cmd_joint(3, 90.0)])
        # 取り出したあとに古い角度が残っていない。
        self.assertEqual(tx.drain(), [])

    def test_ten_axes_collapse_a_burst(self) -> None:
        """0.10 秒ごとに 10 軸を積む流れを、軸数ぶんの最新に縮める。"""
        tx = _UsbTxQueue()
        for _ in range(50):
            for channel in range(10):
                tx.put(proto.cmd_joint(channel, float(channel) + 1.0))
        drained = tx.drain()
        self.assertEqual(len(drained), 10)
        self.assertEqual(drained, [proto.cmd_joint(ch, float(ch) + 1.0) for ch in range(10)])

    def test_mode_stays_in_order_around_a_replaced_joint(self) -> None:
        """モードは残し、置き換わった関節指令はそのモードより後ろへ出す。"""
        tx = _UsbTxQueue()
        tx.put(proto.cmd_joint(0, 10.0))
        tx.put(proto.cmd_mode(True))
        tx.put(proto.cmd_joint(1, 20.0))
        tx.put(proto.cmd_joint(0, 30.0))
        self.assertEqual(
            tx.drain(),
            [
                proto.cmd_mode(True),
                proto.cmd_joint(1, 20.0),
                proto.cmd_joint(0, 30.0),
            ],
        )

    def test_map_chunks_are_not_collapsed(self) -> None:
        """校正チャンクは同じ軸でも、積んだ順のまま全部出す。"""
        tx = _UsbTxQueue()
        chunks = proto.cmd_map_chunks(2, [(float(i), float(i) + 0.5) for i in range(20)])
        self.assertGreaterEqual(len(chunks), 2)
        for chunk in chunks:
            self.assertIsNone(_joint_channel(chunk))
            tx.put(chunk)
        self.assertEqual(tx.drain(), chunks)

    def test_short_frame_is_kept_in_order(self) -> None:
        """長さが足りない列は関節指令とみなさず、捨てない。"""
        tx = _UsbTxQueue()
        broken = b"\xAA\x55\x88"
        tx.put(proto.cmd_joint(4, 1.0))
        tx.put(broken)
        tx.put(proto.cmd_out(4, True))
        self.assertIsNone(_joint_channel(broken))
        self.assertEqual(
            tx.drain(),
            [proto.cmd_joint(4, 1.0), broken, proto.cmd_out(4, True)],
        )


if __name__ == "__main__":
    unittest.main()
