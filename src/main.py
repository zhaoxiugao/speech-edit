from encode import Encoder
from probe import Probe, Analysis
from models import SpeechDetection
from export import Timeline
import tempfile
from pathlib import Path
from time import sleep
import click
import torch
import sys

torch.backends.cudnn.benchmark=True
torch.backends.cudnn.deterministic=True

def handle_folder(folder_path):
    ACCEPTED_EXTENSIONS = ['.mp4', '.m4v', '.mov', '.avi', '.mpeg', '.webm', '.wmv', '.flv', '.mpg', '.mxf', '.mts']

    folder = Path(folder_path).glob('**/*')
    files = [Path(x).as_posix() for x in folder if x.is_file() and Path(x).suffix.lower() in ACCEPTED_EXTENSIONS]

    return files

def progress(count, total):
    bar_len = 60
    filled_len = int(round(bar_len * count / float(total)))
    percents = round(100.0 * count / float(total), 1)
    bar = '=' * filled_len + '-' * (bar_len - filled_len)
    status = 'Detecting Speech'

    sys.stdout.write('[%s] %s%s ...%s\r' % (bar, percents, '%', status))
    sys.stdout.flush()

    # print(f'{(curr_batch_index / num_batches) * 100}\r', end="")

@click.command()
@click.argument('files', nargs=-1, type=click.Path(exists=True, readable=True,
    resolve_path=True, dir_okay=True))
@click.option( '-o', '--out', required=True, type=click.Path(exists=False,
                resolve_path=True, dir_okay=False))
@click.option('-t', '--threshold', type=float)
def main(files, out, threshold):

    out_files = []
    for file_path in list(files):
        if Path(file_path).is_dir():
            out_files.extend(handle_folder(file_path))
        else:
            out_files.append(file_path)

    analyse_clips = Analysis(out_files).summary()
    output_timeline = Timeline().create_timeline(settings=analyse_clips)

    speech_detector = SpeechDetection(batch_size=8, threshold=threshold, progress_hook=progress)
    speech_detector_cpu = SpeechDetection(batch_size=8, device="cpu", threshold=threshold, progress_hook=progress)
    output_file = open(out, 'w+')

    for i, file_path in enumerate(out_files):

        file_properties = Probe(file_path).run().extract_summary()
        
        temp_dir = tempfile.TemporaryDirectory()
        temp_audio_file = Encoder.wav_audio_temp(file_path, temp_dir.name)

        print(f'Processing File {i + 1} of {len(out_files)}: {file_path}')
        
        for _ in range(0, 3):  # Try two more times if there's an error.
            try:
                speech = speech_detector.run(temp_audio_file).to_frames(file_properties['video']['frame_rate'])
                break
            except Exception as e:
                print(e)

                try:
                    speech = speech_detector_cpu.run(temp_audio_file).to_frames(file_properties['video']['frame_rate'])
                    print("Processed using CPU")
                    break
                except Exception as e:
                    pass
        
        output_timeline.add_file(file_path, speech)
        output_file.seek(0)
        output_file.truncate()
        output_file.write(output_timeline.export())
        temp_dir.cleanup()
    
    output_file.close()

# pylint: disable=no-value-for-parameter
if __name__ == "__main__":
    main()

