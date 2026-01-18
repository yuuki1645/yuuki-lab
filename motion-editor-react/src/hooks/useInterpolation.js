import { useState, useEffect, useRef, useCallback } from 'react';
import { getAngleAtTime } from '../utils/interpolation';
import { moveServos } from '../api/servoApi';
import { INTERPOLATION_INTERVAL } from '../constants';

/**
 * モーション再生とサーボ制御を行うカスタムフック
 * 
 * このフックは以下の機能を提供します:
 * - キーフレームベースのモーション再生
 * - requestAnimationFrameを使用した高精度なタイミング制御
 * - 線形補間による滑らかなサーボ角度の計算
 * - ループ再生と再生速度の調整
 * - 一時停止・再開・停止機能
 * 
 * @param {Array} keyframes - キーフレーム配列（時間順にソート済み）
 *                           各キーフレームは { time: number, angles: { [ch]: angle } } の形式
 * @param {number} duration - モーションの総時間（ミリ秒）
 * @param {string} mode - サーボ制御モード（'logical' または 'physical'）
 *                        デフォルトは 'logical'（論理角）
 * @returns {Object} 再生制御用の状態と関数
 */
export function useInterpolation(keyframes, duration, mode = 'logical') {
  // ========== 状態管理 ==========
  
  /** 再生中かどうかのフラグ */
  const [isPlaying, setIsPlaying] = useState(false);
  
  /** 一時停止中かどうかのフラグ */
  const [isPaused, setIsPaused] = useState(false);
  
  /** 現在の再生時間（ミリ秒）。タイムラインのプレイヘッド位置に使用 */
  const [currentTime, setCurrentTime] = useState(0);
  
  /** ループ再生が有効かどうか */
  const [loop, setLoop] = useState(false);
  
  /** 再生速度の倍率（0.25x ～ 2.0x） */
  const [playbackSpeed, setPlaybackSpeed] = useState(1.0);
  
  // ========== 参照（再レンダリングを避けるため） ==========
  
  /** requestAnimationFrameのIDを保持（クリーンアップ時に使用） */
  const animationFrameRef = useRef(null);
  
  /** 再生開始時のタイムスタンプ（performance.now()の値）
   *  一時停止から再開する際に、経過時間を計算するために使用 */
  const startTimeRef = useRef(null);
  
  /** 一時停止時の経過時間（ミリ秒）
   *  一時停止から再開する際に、この時間から継続する */
  const pausedTimeRef = useRef(0);
  
  // ========== 再生制御関数 ==========
  
  /**
   * 再生を開始または再開
   * - 一時停止中の場合: 一時停止位置から再開
   * - 停止中の場合: 最初（0秒）から再生開始
   */
  const play = useCallback(() => {
    if (isPaused) {
      // 一時停止から再開する場合
      setIsPaused(false);
      // 現在のタイムスタンプから、一時停止時の経過時間を引いた値を開始時刻として設定
      // これにより、経過時間の計算が正しく継続される
      startTimeRef.current = performance.now() - pausedTimeRef.current;
    } else {
      // 最初から再生する場合
      setIsPlaying(true);
      setCurrentTime(0);
      // 現在のタイムスタンプを開始時刻として記録
      startTimeRef.current = performance.now();
      pausedTimeRef.current = 0;
    }
  }, [isPaused]);
  
  /**
   * 再生を停止し、時間を0にリセット
   * - アニメーションループを停止
   * - すべての状態をリセット
   */
  const stop = useCallback(() => {
    setIsPlaying(false);
    setIsPaused(false);
    setCurrentTime(0);
    pausedTimeRef.current = 0;
    // 実行中のアニメーションフレームがあればキャンセル
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
    }
  }, []);
  
  /**
   * 再生を一時停止
   * - 現在の再生位置を保持
   * - アニメーションループは停止するが、時間はリセットしない
   */
  const pause = useCallback(() => {
    setIsPaused(true);
    setIsPlaying(false);
  }, []);
  
  // ========== アニメーションループ ==========
  
  /**
   * メインのアニメーションループ
   * 
   * requestAnimationFrameを使用して、ブラウザの描画タイミングに同期して
   * モーションの再生とサーボ制御を行います。
   * 
   * 処理の流れ:
   * 1. 経過時間を計算（再生速度を考慮）
   * 2. 現在時間がモーションの終了時間を超えた場合、ループ処理または停止
   * 3. 一定間隔（INTERPOLATION_INTERVAL）ごとにサーボ角度を計算して送信
   * 4. 次のフレームをリクエスト
   */
  useEffect(() => {
    // 再生中でない、または一時停止中の場合は何もしない
    if (!isPlaying || isPaused) {
      // 実行中のアニメーションフレームがあればキャンセル
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      return;
    }
    
    /** 最後にサーボを更新した時刻（タイムスタンプ）
     *  INTERPOLATION_INTERVALごとにサーボを更新するために使用 */
    let lastUpdateTime = 0;
    
    /**
     * アニメーションループのコールバック関数
     * ブラウザの描画タイミングごとに呼び出される
     * 
     * @param {number} timestamp - requestAnimationFrameから渡される現在のタイムスタンプ
     *                             performance.now()と同等の高精度な時間
     */
    const animate = (timestamp) => {
      // 開始時刻が設定されていない場合（初回フレーム）、現在時刻を開始時刻として設定
      if (!startTimeRef.current) {
        startTimeRef.current = timestamp;
      }
      
      // 経過時間を計算（再生速度を考慮）
      // elapsed: 開始時刻からの経過時間（ミリ秒）に再生速度を掛けた値
      const elapsed = (timestamp - startTimeRef.current) * playbackSpeed;
      
      // 新しい再生時間 = 一時停止時の経過時間 + 再開後の経過時間
      const newTime = pausedTimeRef.current + elapsed;
      
      // ========== ループ処理 ==========
      // モーションの終了時間に達した場合の処理
      if (newTime >= duration) {
        if (loop) {
          // ループが有効な場合: 最初に戻る
          pausedTimeRef.current = 0;
          startTimeRef.current = timestamp; // 新しい開始時刻を設定
          setCurrentTime(0);
        } else {
          // ループが無効な場合: 停止
          stop();
          return; // アニメーションループを終了
        }
      } else {
        // モーションの終了時間に達していない場合: 現在時間を更新
        setCurrentTime(newTime);
        // 一時停止時に使用するため、現在の経過時間を保存
        pausedTimeRef.current = newTime;
      }
      
      // ========== サーボ制御 ==========
      // 一定間隔（INTERPOLATION_INTERVAL）ごとにサーボを更新
      // これにより、サーボAPIへの過剰なリクエストを防ぎ、パフォーマンスを向上
      if (timestamp - lastUpdateTime >= INTERPOLATION_INTERVAL) {
        // 現在時間における各サーボの角度を計算（線形補間）
        // 戻り値: { [ch]: angle } の形式（例: { 0: 45.5, 1: 90.0, ... }）
        const angles = getAngleAtTime(keyframes, newTime);
        
        // 角度データが存在する場合のみサーボを制御
        if (Object.keys(angles).length > 0) {
          // 複数のサーボを同時に制御
          // mode: 'logical' の場合は論理角、'physical' の場合は物理角を送信
          moveServos(angles, mode).catch(err => {
            // エラーが発生した場合はコンソールに出力（再生は継続）
            console.error('Failed to move servos:', err);
          });
        }
        
        // 最後の更新時刻を記録
        lastUpdateTime = timestamp;
      }
      
      // 次のフレームをリクエスト（アニメーションループを継続）
      animationFrameRef.current = requestAnimationFrame(animate);
    };
    
    // アニメーションループを開始
    animationFrameRef.current = requestAnimationFrame(animate);
    
    // クリーンアップ関数: コンポーネントのアンマウント時や依存配列の値が変更された時に実行
    return () => {
      // 実行中のアニメーションフレームがあればキャンセル
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [
    isPlaying,      // 再生状態が変更されたら再実行
    isPaused,       // 一時停止状態が変更されたら再実行
    keyframes,      // キーフレームが変更されたら再実行
    duration,       // モーション時間が変更されたら再実行
    loop,           // ループ設定が変更されたら再実行
    playbackSpeed,  // 再生速度が変更されたら再実行
    mode,           // サーボ制御モードが変更されたら再実行
    stop            // stop関数が変更されたら再実行（useCallbackでメモ化されている）
  ]);
  
  // ========== 戻り値 ==========
  // コンポーネントで使用する状態と関数を返す
  return {
    isPlaying,        // 再生中かどうか
    isPaused,         // 一時停止中かどうか
    currentTime,      // 現在の再生時間（ミリ秒）
    loop,             // ループ設定
    playbackSpeed,    // 再生速度
    setLoop,          // ループ設定を変更する関数
    setPlaybackSpeed, // 再生速度を変更する関数
    play,             // 再生開始/再開関数
    pause,            // 一時停止関数
    stop,             // 停止関数
  };
}