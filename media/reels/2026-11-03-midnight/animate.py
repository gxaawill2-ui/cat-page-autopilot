"""Daily Purr original painted 2D rig / deterministic 24-fps animation.
No video API, stock footage, music samples or crossfade animation.
"""
from pathlib import Path
import math, json, hashlib, subprocess, wave, argparse
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageEnhance

ROOT=Path(__file__).resolve().parent
W,H,FPS,DURATION=1080,1920,24,15
GROUND=1430.
def smooth(x):
    x=max(0.,min(1.,x));return x*x*x*(10+x*(-15+6*x))
def ramp(t,a,b):return smooth((t-a)/(b-a))
def lerp(a,b,u):return np.array(a,dtype=float)*(1-u)+np.array(b,dtype=float)*u
def pulse(t,c,w):return max(0.,1-abs(t-c)/w)

BOXES={'body':(8,62,418,360),'head':(414,4,768,360),'tail':(776,38,1123,360),
       'fore_upper':(88,387,316,702),'fore_lower':(457,401,643,700),
       'fore_paw':(794,487,1022,657),'thigh':(1121,382,1390,706),
       'shin':(84,737,275,1046),'hind_paw':(426,812,667,991),
       'far_fore_paw':(791,825,1012,985),'far_hind_paw':(1130,815,1373,987)}
ATLAS=Image.open(ROOT/'assets/ajiu-rig-atlas.webp').convert('RGBA')
SPRITES={k:ATLAS.crop(b) for k,b in BOXES.items()}
BG=ImageOps.fit(Image.open(ROOT/'assets/night-kitchen.webp').convert('RGB'),(W,H),method=Image.Resampling.LANCZOS).convert('RGBA')
FONT=ROOT/'assets/subtitle-tc.otf'
TITLE=ImageFont.truetype(str(FONT),54)
CAPTION=ImageFont.truetype(str(FONT),47)
SMALL=ImageFont.truetype(str(FONT),24)

def affine_sprite(canvas,sprite,anchor,world,matrix):
    """Place a painted part with a real affine skeletal transform."""
    M=np.array(matrix,dtype=float);anchor=np.array(anchor);world=np.array(world)
    corners=np.array([[0,0],[sprite.width,0],[sprite.width,sprite.height],[0,sprite.height]])
    points=(corners-anchor)@M.T+world
    x0,y0=np.floor(points.min(axis=0)-2).astype(int)
    x1,y1=np.ceil(points.max(axis=0)+2).astype(int)
    inv=np.linalg.inv(M);offset=anchor+inv@(np.array([x0,y0])-world)
    coeff=(inv[0,0],inv[0,1],offset[0],inv[1,0],inv[1,1],offset[1])
    tile=sprite.transform((max(1,x1-x0),max(1,y1-y0)),Image.Transform.AFFINE,coeff,Image.Resampling.BICUBIC)
    canvas.alpha_composite(tile,(int(x0),int(y0)))

def rotated(canvas,sprite,pivot,world,scale,angle,scale_x=1.):
    a=math.radians(angle);c,s=math.cos(a),math.sin(a)
    affine_sprite(canvas,sprite,pivot,world,[[scale*c*scale_x,-scale*s],[scale*s*scale_x,scale*c]])

def segment(canvas,name,a,b,width_scale=0.45,dark=False):
    im=SPRITES[name]
    if dark:im=ImageEnhance.Brightness(im).enhance(.77)
    anchors={'fore_upper':((153,32),(80,275)), 'fore_lower':((75,25),(127,265)),
             'thigh':((165,40),(91,270)), 'shin':((105,25),(113,275))}
    sa,sb=map(np.array,anchors[name]);sv=sb-sa;su=sv/np.linalg.norm(sv)
    a,b=np.array(a),np.array(b);v=b-a;length=np.linalg.norm(v);u=v/length
    M=np.outer(u,su)*(length/np.linalg.norm(sv))+np.outer([u[1],-u[0]],[su[1],-su[0]])*width_scale
    affine_sprite(canvas,im,sa,a,M)

def ik(a,b,l1,l2,bend):
    a,b=np.array(a),np.array(b);v=b-a;d=np.linalg.norm(v)
    if d>l1+l2-.5: raise ValueError('Unreachable joint '+str(d))
    u=v/max(d,1);x=(d*d+l1*l1-l2*l2)/(2*max(d,1));h=math.sqrt(max(0,l1*l1-x*x))
    return a+u*x+np.array([-u[1],u[0]])*h*bend

def blink_amount(t):
    return max([smooth(pulse(t,c,w)) for c,w in [(1.65,.14),(3.12,.13),(6.25,.14),(11.85,.15),(14.1,.24)]])

def head_sprite(t,shock):
    im=SPRITES['head'].copy()
    blink=blink_amount(t)
    if blink>.005:
        for box in [(173,159,255,224),(289,161,319,225)]:
            x0,y0,x1,y1=box;bw,bh=x1-x0,y1-y0
            original=im.crop(box)
            fill=SPRITES['head'].crop((x0,134,x1,155)).resize((bw,bh),Image.Resampling.BICUBIC)
            mask=Image.new('L',(bw,bh));ImageDraw.Draw(mask).ellipse((0,0,bw-1,bh-1),fill=255)
            mask=mask.filter(ImageFilter.GaussianBlur(1.2));im.paste(fill,(x0,y0),mask)
            hh=max(2,round(bh*(1-blink)))
            eye=original.resize((bw,hh),Image.Resampling.LANCZOS)
            small_mask=mask.resize((bw,hh),Image.Resampling.LANCZOS)
            im.paste(eye,(x0,y0+(bh-hh)//2),small_mask)
    # Local ear deformation only; face landmarks are not regenerated per frame.
    ear_shift=3*math.sin(t*3.3)+5*math.sin(t*1.2)
    def sample(x,y):
        near=max(0,1-abs(x-110)/115)*max(0,1-y/170)
        far=max(0,1-abs(x-285)/65)*max(0,1-y/160)
        dx=near*(ear_shift-25*shock)+far*(-ear_shift*.5-9*shock)
        dy=(near+far)*14*shock
        return x-dx,y-dy
    mesh=[];step=32
    for y in range(0,im.height,step):
        for x in range(0,im.width,step):
            xx,yy=min(x+step,im.width),min(y+step,im.height)
            mesh.append(((x,y,xx,yy),sum((sample(*q) for q in [(x,y),(x,yy),(xx,yy),(xx,y)]),())))
    return im.transform(im.size,Image.Transform.MESH,mesh,Image.Resampling.BICUBIC)

def foot_motion(t,offset,phase):
    distance=180*ramp(t,4.35,8.05);u=distance/90+phase
    cycle=math.floor(u);f=u-cycle
    travel=90*(cycle+smooth((f-.66)/.34))
    initial=90*(math.floor(phase)+smooth((phase%1-.66)/.34))
    lift=math.sin(math.pi*max(0,min(1,(f-.66)/.34)))**1.5*34 if f>.66 else 0
    return np.array([350+offset+travel-initial,GROUND-lift]),f<=.66

def can_image(angle=0):
    S=3;im=Image.new('RGBA',(170*S,150*S));d=ImageDraw.Draw(im)
    d.rounded_rectangle((22*S,27*S,115*S,124*S),radius=20*S,fill='#c7c6ad',outline='#685747',width=2*S)
    for x in range(25,115):
        k=(x-25)/90;shade=int(165+65*math.sin(k*math.pi))
        d.line((x*S,40*S,x*S,113*S),fill=(shade,shade-3,shade-20),width=S)
    d.ellipse((53*S,21*S,157*S,125*S),fill='#e2e1cb',outline='#6b5d49',width=2*S)
    d.ellipse((61*S,29*S,149*S,117*S),fill='#d9bf84',outline='#a38a5b',width=2*S)
    # Small original fish mark, no brand or misleading generated lettering.
    label=Image.new('RGBA',im.size);ld=ImageDraw.Draw(label)
    ld.ellipse((89*S,62*S,119*S,83*S),fill='#c57555')
    ld.polygon([(88*S,72*S),(76*S,61*S),(76*S,83*S)],fill='#c57555')
    ld.ellipse((111*S,67*S,114*S,70*S),fill='#4c453a')
    label=label.rotate(-angle,center=(105*S,73*S),resample=Image.Resampling.BICUBIC)
    im.alpha_composite(label)
    d.arc((79*S,39*S,132*S,102*S),200,290,fill='#fff9d9',width=2*S)
    return im.resize((170,150),Image.Resampling.LANCZOS)
CAN=can_image()

def can_roll(t):
    # Quintic onset is smooth, the travel settles before the reaction resolves.
    return 48*(1-(1-ramp(t,9.20,9.95))**2)

def pose(t):
    walk=180*ramp(t,4.35,8.05)
    startle=(ramp(t,9.28,9.43)-ramp(t,10.7,11.3))
    stretch=.68*ramp(t,11.55,12.65)*(1-.2*ramp(t,13.3,14.4))
    root=350+walk-15*startle-10*stretch
    bob=4*math.sin(walk/90*math.pi*2)*math.sin(math.pi*min(walk/180,1))
    breath=2.0*math.sin(t*2.1)
    hip=np.array([root-112,1190+bob-48*stretch-6*startle+breath*.5])
    shoulder=np.array([root+120,1180+bob+39*stretch-9*startle+breath])
    feet={};contacts={}
    for k,offset,phase in [('near_fore',132,0),('far_fore',164,.5),('near_hind',-130,.5),('far_hind',-83,0)]:
        feet[k],contacts[k]=foot_motion(t,offset,phase)
        if k.startswith('far'): feet[k][1]-=18
    # Paw makes contact before the can moves, follows the push, then recoils.
    reach=ramp(t,8.05,9.18)
    roll=can_roll(t)
    pushed=np.array([790+roll*.7,1365.])
    recoil=ramp(t,9.38,9.85)
    target=lerp(pushed,(715,1336),recoil)
    feet['near_fore']=lerp(feet['near_fore'],target,reach)
    contacts['near_fore']=contacts['near_fore'] and reach<.000001
    # Stagger the two landing steps; each foot stops moving after contact.
    for key,offset,a,b,extension in [('far_fore',164,10.40,11.08,30),
                                    ('near_fore',132,10.78,11.52,64)]:
        place=ramp(t,a,b)
        end=np.array([350+180+offset+extension,GROUND-(18 if key.startswith('far') else 0)])
        feet[key]=lerp(feet[key],end,place)
        feet[key][1]-=24*math.sin(math.pi*place)
        if 0<place<1:contacts[key]=False
        elif place==1:contacts[key]=True
    return dict(root=root,hip=hip,shoulder=shoulder,feet=feet,contacts=contacts,shock=startle,stretch=stretch)

def render(t,debug=False):
    canvas=BG.copy();p=pose(t);hip,sh=p['hip'],p['shoulder']
    shadow=Image.new('RGBA',(W,H));sd=ImageDraw.Draw(shadow)
    sd.ellipse((p['root']-240,GROUND-13,p['root']+300,GROUND+21),fill=(44,28,22,43))
    for f in p['feet'].values():
        opacity=round(42*max(.12,1-abs(GROUND-f[1])/90))
        sd.ellipse((f[0]-29,GROUND-5,f[0]+51,GROUND+10),fill=(38,24,20,opacity))
    shadow=shadow.filter(ImageFilter.GaussianBlur(9));canvas.alpha_composite(shadow)
    tail=SPRITES['tail'];rotated(canvas,tail,(35,278),hip+(-45,-75),.56,-7+6*math.sin(t*1.8)+8*p['shock'])
    metadata={'time':t,'feet':{},'joints':{}}
    def leg(key,near,fore):
        foot=p['feet'][key];a=(sh if fore else hip).copy()
        if not near:a+=np.array([18,-12])
        ankle=foot+np.array([-6,-34 if near else -29])
        l1,l2=(116,146) if fore else (136,142)
        knee=ik(a,ankle,l1,l2,1 if fore else -1)
        segment(canvas,'fore_upper' if fore else 'thigh',a,knee,.43 if near else .38,not near)
        segment(canvas,'fore_lower' if fore else 'shin',knee,ankle,.39 if near else .35,not near)
        paw=SPRITES[('fore_paw' if fore else 'hind_paw') if near else ('far_fore_paw' if fore else 'far_hind_paw')]
        if not near:paw=ImageEnhance.Brightness(paw).enhance(.79)
        lift=max(0,(GROUND-(18 if not near else 0))-foot[1])
        paw_angle=-min(12,lift*.24) if t<8.05 else (-7*p['shock'] if key=='near_fore' else 0)
        rotated(canvas,paw,(paw.width*.37,paw.height*.91),foot,.40 if near else .35,paw_angle)
        metadata['feet'][key]={'x':float(foot[0]),'y':float(foot[1]),'contact':bool(p['contacts'][key])}
        metadata['joints'][key]=[a.tolist(),knee.tolist(),ankle.tolist()]
        if debug:
            d=ImageDraw.Draw(canvas);d.line([tuple(a),tuple(knee),tuple(ankle)],fill='cyan',width=3)
    leg('far_hind',False,False);leg('far_fore',False,True)
    body=SPRITES['body'];v=sh-hip;u=v/np.linalg.norm(v)
    M=np.column_stack((v/235,np.array([-u[1],u[0]])*.86))
    affine_sprite(canvas,body,(75,164),hip+(-5,-25),M)
    leg('near_hind',True,False);leg('near_fore',True,True)
    # Can is stationary until contact, then decelerates rolling with angle=s/r.
    roll=can_roll(t)
    cpos=np.array([885+roll,GROUND-52*.86])
    sd2=Image.new('RGBA',(W,H));dd=ImageDraw.Draw(sd2);dd.ellipse((cpos[0]-54,GROUND-5,cpos[0]+50,GROUND+12),fill=(39,26,16,70))
    canvas.alpha_composite(sd2.filter(ImageFilter.GaussianBlur(5)))
    rotated(canvas,can_image(roll/(52*.86)*180/math.pi),(105,73),cpos,.86,0)
    head=head_sprite(t,p['shock'])
    angle=-7*ramp(t,.4,1.8)+5*ramp(t,2.1,3.2)+8*ramp(t,8,9.1)-9*p['shock']+10*p['stretch']-8*ramp(t,13.1,14.5)
    flinch=math.exp(-max(0,t-9.30)*8)*math.sin(max(0,t-9.30)*26) if t>=9.30 else 0
    neck=sh+np.array([5-5*p['shock'],-20-7*p['shock']])
    angle+=2.5*flinch
    rotated(canvas,head,(100,300),neck,.87,angle,1-.035*ramp(t,13,14.3))
    # Continuous gentle camera movement, not the source of character motion.
    zoom=1+.035*ramp(t,0,4)+.025*ramp(t,8.8,10)
    vw,vh=W/zoom,H/zoom;cx,cy=565,1110
    x0=(W-vw)*cx/W;y0=(H-vh)*cy/H
    canvas=canvas.transform((W,H),Image.Transform.EXTENT,(x0,y0,x0+vw,y0+vh),Image.Resampling.BICUBIC)
    overlay=Image.new('RGBA',(W,H));d=ImageDraw.Draw(overlay)
    d.text((76,94),'DAILY PURR',font=SMALL,fill=(255,242,211,230),stroke_width=1,stroke_fill=(34,27,30,150))
    d.text((73,134),'阿橘的深夜罐罐任務',font=TITLE,fill=(255,244,221,255),stroke_width=2,stroke_fill=(31,29,37,170))
    text=('主人以為阿橘睡著了……' if t<4 else '其實牠正在執行秘密任務。' if t<9.45 else '任務失敗，啟動裝無辜模式。')
    d.rounded_rectangle((65,1535,1015,1645),radius=22,fill=(25,28,39,210),outline=(239,208,145,90),width=1)
    box=d.textbbox((0,0),text,font=CAPTION);width=box[2]-box[0]
    d.text(((W-width)/2,1558),text,font=CAPTION,fill=(255,246,222,255),stroke_width=1,stroke_fill=(22,25,35,255))
    canvas.alpha_composite(overlay)
    return canvas.convert('RGB'),metadata

def audio():
    sr=48000;n=DURATION*sr;data=np.zeros((n,2),np.float64);rng=np.random.default_rng(81)
    def add(t,dur,freq,amp=.1,kind='tone',pan=0):
        nn=int(dur*sr);x=np.arange(nn)/sr
        if kind=='noise':y=rng.normal(0,1,nn)*np.exp(-x*40)
        elif kind=='metal':y=(np.sin(2*np.pi*freq*x)+.45*np.sin(2*np.pi*freq*2.71*x)+.18*np.sin(2*np.pi*freq*4.1*x))*np.exp(-x*7)
        else:y=(np.sin(2*np.pi*freq*x)+.22*np.sin(2*np.pi*freq*2*x))*np.exp(-x*5)*np.minimum(x*140,1)
        y*=amp;idx=int(t*sr);nn=min(nn,n-idx)
        if nn<=0:return
        data[idx:idx+nn,0]+=y[:nn]*math.sqrt((1-pan)/2);data[idx:idx+nn,1]+=y[:nn]*math.sqrt((1+pan)/2)
    for t,f in [(0.3,392),(1.4,523.25),(2.7,587.33),(4.4,392),(5.6,440),(7,523.25),(8.4,587.33)]:add(t,.7,f,.035)
    for t in [4.8,5.45,6.1,6.8,7.45]:add(t,.14,100,.055,'noise',-.1)
    for t,f,a in [(9.23,1100,.19),(9.43,1450,.12),(9.69,920,.08)]:add(t,.7,f,a,'metal',.5)
    for t,f in [(10.1,349.23),(10.3,329.63),(12.3,392),(12.55,523.25),(13.4,659.25),(14.1,783.99)]:add(t,.65,f,.065)
    data*=np.minimum(np.arange(n)/(sr*.1),1)[:,None]*np.minimum((n-np.arange(n))/(sr*.4),1)[:,None]
    peak=float(np.max(np.abs(data)));data*=min(1,.88/max(peak,.01))
    with wave.open(str(ROOT/'original-sound.wav'),'wb') as f:f.setnchannels(2);f.setsampwidth(2);f.setframerate(sr);f.writeframes((data*32767).astype('<i2').tobytes())

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--keys',action='store_true');args=ap.parse_args();(ROOT/'qa').mkdir(exist_ok=True)
    if args.keys:
        for t in [0,1.7,3.3,4.8,6.2,8.5,9.3,9.7,11.5,12.6,14.1,14.8]:
            im,_=render(t);im.resize((540,960)).save(ROOT/'qa'/('key-%04d.jpg'%int(t*10)),quality=92)
        return
    audio();out=ROOT/'ajiu-midnight-mission-v2.mp4'
    cmd=['ffmpeg','-y','-loglevel','error','-f','rawvideo','-vcodec','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-i',str(ROOT/'original-sound.wav'),'-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-movflags','+faststart','-shortest',str(out)]
    pipe=subprocess.Popen(cmd,stdin=subprocess.PIPE);track=[]
    try:
        for i in range(FPS*DURATION):
            im,m=render(i/FPS);pipe.stdin.write(im.tobytes());track.append(m)
            if i%24==0:print('rendered',i,'of',FPS*DURATION,flush=True)
    finally:pipe.stdin.close()
    if pipe.wait()!=0:raise RuntimeError('FFmpeg failed')
    (ROOT/'qa/motion-track.json').write_text(json.dumps(track))
    print(out,hashlib.sha256(out.read_bytes()).hexdigest(),flush=True)

if __name__=='__main__':main()
