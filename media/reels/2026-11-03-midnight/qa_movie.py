"""Decode every delivered frame, build temporal review sheets and motion checks."""
from pathlib import Path
import subprocess,json,hashlib,wave
import numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parent
movie=ROOT/'ajiu-midnight-mission-v2.mp4'
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(movie)]))
subprocess.run(['ffmpeg','-v','error','-i',str(movie),'-f','null','-'],check=True)
track=json.loads((ROOT/'qa/motion-track.json').read_text())
drift=[];bone_error=[];max_foot_step=0
for a,b in zip(track,track[1:]):
    for key in a['feet']:
        x,y=a['feet'][key],b['feet'][key]
        step=float(np.linalg.norm(np.array([x['x'],x['y']])-np.array([y['x'],y['y']])))
        max_foot_step=max(max_foot_step,step)
        if x['contact'] and y['contact']:drift.append(step)
for row in track:
    for key,(a,k,b) in row['joints'].items():
        expected=(116,146) if 'fore' in key else (136,142)
        bone_error.extend([abs(np.linalg.norm(np.array(k)-a)-expected[0]),abs(np.linalg.norm(np.array(b)-k)-expected[1])])
# Inspect all 360 output frames, grouped into 24-frame temporal sheets.
cmd=['ffmpeg','-v','error','-i',str(movie),'-vf','crop=980:650:70:820,scale=240:160','-f','rawvideo','-pix_fmt','rgb24','-']
p=subprocess.Popen(cmd,stdout=subprocess.PIPE);sheets=[];count=0;hashes=[]
for second in range(15):
    sheet=Image.new('RGB',(8*240,3*180),(23,25,31));d=ImageDraw.Draw(sheet)
    for j in range(24):
        raw=p.stdout.read(240*160*3)
        if len(raw)!=240*160*3:raise ValueError('Decoded frame missing')
        im=Image.frombytes('RGB',(240,160),raw);hashes.append(hashlib.sha256(raw).hexdigest())
        x,y=(j%8)*240,(j//8)*180;sheet.paste(im,(x,y+20));d.text((x+5,y+3),f'{count:03d} | {count/24:.3f}s',fill='white');count+=1
    path=ROOT/'qa'/f'all-frames-{second:02d}.jpg';sheet.save(path,quality=93);sheets.append(path.name)
if p.wait()!=0:raise ValueError('Decode failed')
cmd=['ffmpeg','-v','error','-i',str(movie),'-vf','fps=1,scale=270:480','-f','rawvideo','-pix_fmt','rgb24','-']
p=subprocess.Popen(cmd,stdout=subprocess.PIPE);sheet=Image.new('RGB',(1350,1500),(20,22,27));d=ImageDraw.Draw(sheet)
for i in range(15):
    raw=p.stdout.read(270*480*3)
    if len(raw)!=270*480*3:raise ValueError('Overview frame missing')
    sheet.paste(Image.frombytes('RGB',(270,480),raw),((i%5)*270,(i//5)*500+20));d.text(((i%5)*270+7,(i//5)*500+3),str(i)+' seconds',fill='white')
if p.wait()!=0:raise ValueError('Overview failed')
sheet.save(ROOT/'qa/full-film-overview.jpg',quality=94)
with wave.open(str(ROOT/'original-sound.wav')) as f:
    samples=np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').astype(float)/32768
    audio={'seconds':f.getnframes()/f.getframerate(),'channels':f.getnchannels(),'sample_rate':f.getframerate(),'peak':float(np.max(np.abs(samples))),'origin':'original deterministic synthesis, no samples'}
report={'movie_sha256':hashlib.sha256(movie.read_bytes()).hexdigest(),'bytes':movie.stat().st_size,
        'streams':[{k:s.get(k) for k in ['codec_name','width','height','r_frame_rate','duration','nb_frames']}for s in probe['streams']],
        'duration':probe['format']['duration'],'all_frames_decoded':count,'unique_character_crop_frames':len(set(hashes)),
        'max_stance_paw_drift_world_px':max(drift,default=None),'max_two_link_bone_length_error_px':max(bone_error),
        'max_swing_paw_step_px':max_foot_step,'audio':audio,'all_frame_review_sheets':sheets,
        'technical_pass':bool(count==360 and max(drift,default=0)<.01 and max(bone_error)<.01),
        'artistic_quality':'PENDING full temporal visual review; technical pass is not a natural-motion approval',
        'facebook_write_calls':0}
(ROOT/'qa/technical-report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
