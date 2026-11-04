"""Original Daily Purr 12-second viral-style cut of the existing 2D-IK B animation.

No image/video/Meta API, no assets copied from any third-party Reel.
Run: python3 scripts/viral_reel_edit.py --keys
     python3 scripts/viral_reel_edit.py
This is a NEW derived render; it NEVER edits the 15-second master.
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, shutil, subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DIR=ROOT/"media/reels/2026-11-03-midnight"
FPS=24
# Source frame index start inclusive / end exclusive. Edit retains real 1:1 pose timing.
# Action first -> rewind -> full physical payoff. No slideshow or speed warp.
SEGMENTS=(
    (220,244,"cold_open"),    # can suddenly moves, immediate visual surprise
    (91,220,"flashback"),     # stalking and walking, full continuous paw movement
    (220,355,"payoff"),       # the same accident resolves into a guilty-cat reaction
)
TOTAL_FRAMES=sum(b-a for a,b,_ in SEGMENTS)
OUTPUT=DIR/"previews/ajiu-viral-hook-story-v1.mp4"

def timeline():
    for a,b,label in SEGMENTS:
        for k in range(a,b):
            yield k,label

def validate_timeline():
    assert FPS==24 and TOTAL_FRAMES==288
    for a,b,label in SEGMENTS:
        if not 0<=a<b<=360:
            raise ValueError("Segment outside source 15-second film")
    # Same source fps and 1:1 increments: no repeating stills to fake movement.
    for (a,b,_),(c,d,_) in zip(SEGMENTS,SEGMENTS[1:]):
        if b-a<20 or d-c<20:
            raise ValueError("An excessively short source segment")

def load_source():
    script=DIR/"animate.py"
    if not script.exists():
        raise FileNotFoundError("Saved B-scheme animation source is missing; never replace artwork")
    for name in ("ajiu-rig-atlas.webp","night-kitchen.webp","subtitle-tc.otf"):
        if not (DIR/"assets"/name).is_file():
            raise FileNotFoundError("Saved original animation asset missing: "+name)
    spec=importlib.util.spec_from_file_location("daily_purr_saved_B_animation",script)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    if (module.W,module.H,module.FPS)!=(1080,1920,24):
        raise ValueError("Unexpected original animation dimensions or FPS")
    return module

def overlay(im,src,label,i,frame_no):
    # Keep key image/action dominant. Text is sparse and inside safe mobile area.
    from PIL import ImageDraw, ImageFont
    if (label=="cold_open" and i<24) or (label=="flashback" and i<26):
        d=ImageDraw.Draw(im)
        text="罐罐怎麼自己動了？！" if label=="cold_open" else "剛剛發生了什麼事……"
        font=ImageFont.truetype(str(src.FONT),39)
        box=d.textbbox((0,0),text,font=font)
        bw=box[2]-box[0]
        x=max(76, (src.W-bw)//2-26)
        d.rounded_rectangle((x,244,x+bw+52,319),radius=23,fill=(24,28,35,220),outline=(255,211,130,145),width=2)
        d.text((x+26,254),text,font=font,fill=(255,246,224),stroke_width=1,stroke_fill=(11,13,18))
    return im

def trim_audio(src):
    """Retiming existing ORIGINAL synth audio to the same frame-accurate source segments."""
    src.audio()
    original=DIR/"original-sound.wav"
    out=OUTPUT.parent/"ajiu-viral-original-sound.wav"
    filters=[]
    for j,(a,b,_) in enumerate(SEGMENTS):
        filters.append("[0:a]atrim=start=%.9f:end=%.9f,asetpts=PTS-STARTPTS[a%d]"%(a/FPS,b/FPS,j))
    filters.append("".join("[a%d]"%j for j in range(len(SEGMENTS)))+"concat=n=3:v=0:a=1[out]")
    cmd=["ffmpeg","-y","-loglevel","error","-i",str(original),
         "-filter_complex",";".join(filters),"-map","[out]","-ar","48000",str(out)]
    subprocess.run(cmd,check=True)
    return out

def write_manifest(video=None):
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    data={
        "project":"Daily Purr / original orange-cat B animation",
        "edit":"12s curiosity cold-open -> flashback -> original punchline",
        "source":"media/reels/2026-11-03-midnight/animate.py and existing original generated rig/background",
        "fps":FPS,"frames":TOTAL_FRAMES,"seconds":TOTAL_FRAMES/FPS,
        "resolution":[1080,1920],"segments":[{"first":a,"last_exclusive":b,"type":n} for a,b,n in SEGMENTS],
        "originality":"No reference creator's media, audio, logo or distinctive sequence copied",
        "production":"Preview only, DO NOT upload before full frame-by-frame and full-playback QA",
        "facebook_writes":0,"paid_video_api_calls":0,"additional_cost_ntd":0,
        "rendered_sha256":hashlib.sha256(video.read_bytes()).hexdigest() if video and video.exists() else None
    }
    (OUTPUT.parent/"viral-cut-manifest.json").write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    return data

def main():
    validate_timeline()
    parser=argparse.ArgumentParser()
    parser.add_argument("--keys",action="store_true",help="Render 4 thumbnails only; no video or Meta calls")
    args=parser.parse_args()
    src=load_source()
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    if args.keys:
        for i in (0,24,153,271):
            k,label=list(timeline())[i]
            im,_=src.render(k/FPS)
            im=overlay(im,src,label,i,i)
            im.resize((540,960)).save(OUTPUT.parent/("viral-cut-key-%03d.jpg"%i),quality=90)
        write_manifest()
        return
    if not shutil.which("ffmpeg"):
        raise RuntimeError("Local FFmpeg not present; no render or upload attempted")
    audio=trim_audio(src)
    cmd=["ffmpeg","-y","-loglevel","error","-f","rawvideo","-vcodec","rawvideo",
         "-pix_fmt","rgb24","-s","1080x1920","-r",str(FPS),"-i","-",
         "-i",str(audio),"-c:v","libx264","-preset","medium","-crf","18",
         "-pix_fmt","yuv420p","-c:a","aac","-b:a","160k",
         "-movflags","+faststart","-shortest",str(OUTPUT)]
    proc=subprocess.Popen(cmd,stdin=subprocess.PIPE)
    qa=[]
    try:
        for i,(k,label) in enumerate(timeline()):
            im,pose=src.render(k/FPS)
            im=overlay(im,src,label,i,i)
            proc.stdin.write(im.tobytes())
            if i%24==0:print("rendered",i,"/",TOTAL_FRAMES,flush=True)
            qa.append({"source_frame":k,"edit_frame":i,"segment":label,"feet":pose.get("feet",{})})
    finally:
        proc.stdin.close()
    if proc.wait()!=0 or not OUTPUT.is_file():
        raise RuntimeError("Render failed; do not publish")
    (OUTPUT.parent/"viral-cut-motion-track.json").write_text(json.dumps(qa),encoding="utf-8")
    print(json.dumps(write_manifest(OUTPUT),ensure_ascii=False),flush=True)

if __name__=="__main__":
    main()
