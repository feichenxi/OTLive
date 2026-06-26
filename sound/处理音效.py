import os
import sys

_FFMPEG_BIN = r"D:\mysoft\ffmpeg\bin"
os.environ["PATH"] = _FFMPEG_BIN + os.pathsep + os.environ.get("PATH", "")

import wave
import numpy as np
from pydub import AudioSegment

TARGET_SAMPLE_RATE = 48000
TARGET_SAMPLE_WIDTH = 2
TARGET_CHANNELS = 1
FRAGMENT_DURATION = 0.5
FRAGMENT_STEP = 0.1


def mp3_to_wav(mp3_path, wav_path):
    audio = AudioSegment.from_mp3(mp3_path)
    audio = audio.set_frame_rate(TARGET_SAMPLE_RATE)
    audio = audio.set_sample_width(TARGET_SAMPLE_WIDTH)
    audio = audio.set_channels(TARGET_CHANNELS)
    audio.export(wav_path, format="wav")
    print(f"WAV 已保存: {wav_path}")
    return wav_path


def split_wav_to_fragments(wav_path, output_dir):
    os.makedirs(output_dir, exist_ok=True)

    with wave.open(wav_path, 'rb') as wf:
        sample_rate = wf.getframerate()
        n_channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        n_frames = wf.getnframes()
        raw_data = wf.readframes(n_frames)

    dtype = np.int16 if sample_width == 2 else np.int8
    audio_data = np.frombuffer(raw_data, dtype=dtype)

    if n_channels > 1:
        audio_data = audio_data.reshape(-1, n_channels)

    total_duration = n_frames / sample_rate
    fragment_samples = int(FRAGMENT_DURATION * sample_rate)
    step_samples = int(FRAGMENT_STEP * sample_rate)

    fragment_index = 0
    start_sample = 0

    while start_sample + fragment_samples <= n_frames:
        end_sample = start_sample + fragment_samples

        if n_channels > 1:
            fragment = audio_data[start_sample:end_sample, :]
        else:
            fragment = audio_data[start_sample:end_sample]

        start_time = start_sample / sample_rate
        end_time = end_sample / sample_rate
        filename = f"{fragment_index:04d}_{start_time:.2f}s-{end_time:.2f}s.wav"
        filepath = os.path.join(output_dir, filename)

        with wave.open(filepath, 'wb') as wf_out:
            wf_out.setnchannels(n_channels)
            wf_out.setsampwidth(sample_width)
            wf_out.setframerate(sample_rate)
            wf_out.writeframes(fragment.tobytes())

        fragment_index += 1
        start_sample += step_samples

    print(f"共生成 {fragment_index} 个音频碎片，保存在: {output_dir}")
    return fragment_index


def process_mp3(mp3_path):
    base_name = os.path.splitext(os.path.basename(mp3_path))[0]
    dir_name = os.path.dirname(mp3_path)

    wav_path = os.path.join(dir_name, f"{base_name}.wav")
    fragment_dir = os.path.join(dir_name, base_name)

    print(f"处理文件: {mp3_path}")
    print(f"目标参数: {TARGET_SAMPLE_RATE}Hz, {TARGET_SAMPLE_WIDTH*8}bit, {'单声道' if TARGET_CHANNELS == 1 else '立体声'}")
    print(f"碎片参数: 每段 {FRAGMENT_DURATION}s, 步长 {FRAGMENT_STEP}s")

    mp3_to_wav(mp3_path, wav_path)
    split_wav_to_fragments(wav_path, fragment_dir)

    print("处理完成!")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        target = sys.argv[1]
    else:
        target = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wait.mp3")

    if not os.path.exists(target):
        print(f"文件不存在: {target}")
        sys.exit(1)

    process_mp3(target)