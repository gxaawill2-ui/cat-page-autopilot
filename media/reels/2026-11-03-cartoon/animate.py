from pathlib import Path
import math, subprocess,wave,hashlib
import numpy as np
from PIL import Image,ImageDraw,ImageFont
R=Path(__file__).parent;F=ImageFont.truetype(str(R/'subtitle-tc.otf'),24);S=ImageFont.truetype(str(R/'subtitle-tc.otf'),17)
def ramp(t,a,b):
 u=max(0,min(1,(t-a)/(b-a)));return u*u*(3-2*u)
def curve(d,p,c,w):
 pts=[]
 for u in np.linspace(0,1,40):pts.append(tuple((1-u)**3*p[0][j]+3*(1-u)**2*u*p[1][j]+3*(1-u)*u*u*p[2][j]+u**3*p[3][j] for j in [0,1]))
 d.line(pts,fill=c,width=w,joint='curve')
 for px,py in pts:d.ellipse((px-w/2,py-w/2,px+w/2,py+w/2),fill=c)
def background():
 im=Image.new('RGB',(540,960),'#e9d0b0');d=ImageDraw.Draw(im);d.rectangle((0,0,540,490),fill='#e3e8da')
 d.rounded_rectangle((35,160,260,390),radius=14,fill='#6f9795');d.rectangle((47,172,248,378),fill='#2b4164');d.ellipse((75,193,122,240),fill='#ffe7b1')
 for x,y in [(171,198),(210,240),(83,322),(185,342)]:d.ellipse((x,y,x+3,y+3),fill='#f7e3bf')
 d.line((148,169,148,382),fill='#6f9795',width=8);d.line((44,277,253,277),fill='#6f9795',width=8)
 d.rounded_rectangle((315,174,522,353),radius=12,fill='#be9b7a');d.line((418,180,418,350),fill='#94765c',width=3)
 for x in [402,430]:d.rounded_rectangle((x,252,x+5,280),radius=2,fill='#f2d9ae')
 d.rectangle((0,473,540,505),fill='#bf916d');d.line((0,474,540,474),fill='#f5d3a6',width=7);d.rectangle((0,506,540,607),fill='#b4c3a9')
 for x in [14,194,374]:d.rounded_rectangle((x,520,x+153,593),radius=7,outline='#8f9f85',width=3)
 for y in [667,750,833,916]:d.line((0,y,540,y),fill='#d8bb96',width=2)
 d.ellipse((32,690,510,795),fill='#d3ac8c');d.ellipse((44,696,498,786),fill='#e4c1a0')
 d.rounded_rectangle((316,419,355,471),radius=8,fill='#fcf1d9');d.arc((341,426,368,458),270,90,fill='#fcf1d9',width=6)
 d.rounded_rectangle((430,424,475,472),radius=8,fill='#ba7e62')
 for x in [435,451,469]:curve(d,[(453,432),(x-33,403),(x+17,380),(x,395)],'#729278',11)
 return im
BG=background();O='#e89d4e';C='#fff0cd';B='#795640'
def foot(t,base,ph):
 dist=103*ramp(t,3.5,7.3);u=dist/51.5+ph;k=math.floor(u);f=u-k;v=ramp(f,.62,1)
 return base+51.5*(k+v)-51.5*math.floor(ph),727-10*math.sin(math.pi*v)
def frame(t):
 im=BG.copy();d=ImageDraw.Draw(im);dist=103*ramp(t,3.5,7.3);shock=ramp(t,9.2,9.4)*(1-ramp(t,10.1,10.6));x=163+dist-4*shock;y=651+1.4*math.sin(t*2.2)+1.4*math.sin(dist/51.5*6.28)
 push=ramp(t,7.5,8.95);roll=27*ramp(t,9.02,9.6);back=ramp(t,9.25,9.8);land=ramp(t,10.2,10.8)
 # Rounded continuous limbs; all roots are occluded by the body.
 for i,(base,ph) in enumerate([(112,.5),(145,0),(221,.5),(244,0)]):
  fx,fy=foot(t,base,ph)
  if i==3:
   fx=fx*(1-push)+(393+roll*.3)*push;fy=fy*(1-push)+703*push
   fx=fx*(1-back)+(x+88)*back;fy=fy*(1-back)+694*back
   fx=fx*(1-land)+(x+88)*land;fy=fy*(1-land)+727*land
  ax=x+(-45 if i<2 else 55);color='#cc863f' if i in [0,2] else O
  points=[(ax,y+22),(ax,y+43),(fx-12,fy-14),(fx,fy-6)]
  curve(d,points,B,24);curve(d,points,color,20)
  d.ellipse((fx-13,fy-13,fx+15,fy+2),fill=B);d.ellipse((fx-11,fy-11,fx+13,fy),fill=C)
 tail=[(x-72,y+7),(x-124,y-19),(x-84,y-72),(x-105,y-91+4*math.sin(t*2))]
 curve(d,tail,B,25);curve(d,tail,O,20)
 d.ellipse((x-90,y-53,x+83,y+54),fill=B);d.ellipse((x-87,y-50,x+80,y+51),fill=O)
 d.arc((x-70,y+6,x+62,y+52),0,180,fill='#f4ca88',width=10)
 for sx in [-51,-18,15]:curve(d,[(x+sx,y-46),(x+sx-13,y-30),(x+sx-12,y-13),(x+sx-18,y+1)],'#bf773d',8)
 hx=x+76+1.4*math.sin(t*.9);hy=y-42-5*shock+2*ramp(t,11,12)
 for p,q in [([(hx-49,hy-27),(hx-47,hy-84),(hx-7,hy-51)],[(hx-44,hy-29),(hx-43,hy-76),(hx-12,hy-50)]), ([(hx+10,hy-50),(hx+44,hy-78),(hx+49,hy-18)],[(hx+16,hy-49),(hx+40,hy-70),(hx+44,hy-23)])]:d.polygon(p,fill=B);d.polygon(q,fill=O)
 d.polygon([(hx-38,hy-62),(hx-35,hy-35),(hx-20,hy-49)],fill='#dfaf91');d.polygon([(hx+23,hy-48),(hx+36,hy-59),(hx+39,hy-32)],fill='#dfaf91')
 d.ellipse((hx-58,hy-57,hx+59,hy+53),fill=B);d.ellipse((hx-55,hy-54,hx+56,hy+50),fill=O)
 for dx in [-17,0,17]:curve(d,[(hx+dx,hy-53),(hx+dx-4,hy-43),(hx+dx-4,hy-37),(hx+dx-5,hy-32)],'#bf773d',6)
 d.ellipse((hx-26,hy+6,hx+54,hy+46),fill=C)
 blink=max(max(0,1-abs(t-c)/.14) for c in [1.7,3.05,6.1,10.9,13.7])
 for ex in [hx-13,hx+33]:
  if blink>.55:d.arc((ex-9,hy-12,ex+9,hy+1),0,180,fill=B,width=3)
  else:
   eh=12+3*shock;d.ellipse((ex-7,hy-eh,ex+7,hy+eh),fill='#483d37');d.ellipse((ex-4,hy-8,ex,hy-3),fill='white')
 d.polygon([(hx+9,hy+14),(hx+22,hy+14),(hx+16,hy+21)],fill='#a36b59');d.line((hx+16,hy+20,hx+16,hy+27),fill=B,width=2)
 d.arc((hx+4,hy+20,hx+16,hy+31),0,110,fill=B,width=2);d.arc((hx+16,hy+20,hx+28,hy+31),70,180,fill=B,width=2)
 for yy in [18,27]:d.line((hx-30,hy+yy,hx-48,hy+yy-4),fill='#a57450',width=2)
 cx=429+roll;d.ellipse((cx-23,731,cx+23,739),fill='#b99477');d.rounded_rectangle((cx-22,698,cx+22,732),radius=6,fill='#b6cbbd',outline=B,width=2)
 d.rectangle((cx-20,707,cx+20,724),fill='#f7e9ba');d.ellipse((cx-22,693,cx+22,705),fill='#dfe6d7',outline=B,width=2);d.ellipse((cx-8,710,cx+7,721),fill='#b98063');d.polygon([(cx+6,715),(cx+14,710),(cx+14,721)],fill='#b98063')
 if 9.2<t<9.85:
  for dx,dy in [(-11,-14),(0,-20),(12,-15)]:d.line((hx+dx,hy-98,hx+dx*1.3,hy-98+dy),fill='#a66f50',width=3)
 d.text((34,43),'DAILY PURR',font=S,fill='#6b7769');d.text((34,77),'阿橘的深夜罐罐任務',font=F,fill='#654f42')
 txt='噓……趁主人睡著。' if t<3.5 else '輕一點，再輕一點……' if t<9.2 else '我只是路過，真的。'
 d.rounded_rectangle((35,818,505,882),radius=18,fill='#fcf2de');bb=d.textbbox((0,0),txt,font=F);d.text(((540-bb[2])/2,836),txt,font=F,fill='#705a48')
 return im.resize((1080,1920),Image.Resampling.LANCZOS)
def music():
 sr=48000;n=sr*15;out=np.zeros(n)
 def note(t,m,dur,vol):
  st=int(t*sr);nn=min(int(dur*sr),n-st)
  if nn<=0:return
  u=np.arange(nn)/sr;f=440*2**((m-69)/12);sig=(np.sin(2*np.pi*f*u)+.24*np.sin(4*np.pi*f*u)+.08*np.sin(6*np.pi*f*u))*np.exp(-u*2.5)*np.minimum(u*45,1);out[st:st+nn]+=sig*vol
 melody=[76,79,81,79,74,76,72,74,76,79,83,81,79,76,74,72,76,79,76,72]
 for i,m in enumerate(melody):note(.3+i*.6,m,.95,.095)
 for bar,ch in enumerate([(48,55,60,64),(45,52,57,60),(53,60,65,69),(55,62,67,71),(48,55,60,64)]):
  for j,m in enumerate(ch):note(bar*2.8+j*.16,m,2.5,.045)
 for t in [9.04,9.25]:note(t,95,.25,.075)
 out*=np.minimum(np.arange(n)/(sr*.4),1)*np.minimum((n-np.arange(n))/(sr*.8),1);stereo=np.column_stack([out,out*.94]);stereo=np.clip(stereo,-.9,.9)
 with wave.open(str(R/'original-bgm.wav'),'wb') as f:f.setnchannels(2);f.setsampwidth(2);f.setframerate(sr);f.writeframes((stereo*32767).astype('<i2').tobytes())
if __name__=='__main__':
 import sys
 if '--keys' in sys.argv:
  for t in [0,5.5,8.8,9.5,12]:frame(t).save(R/f'key-{t}.jpg')
 else:
  music();out=R/'daily-purr-2d-cartoon-v4.mp4';p=subprocess.Popen(['ffmpeg','-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s','1080x1920','-r','24','-i','-','-i',str(R/'original-bgm.wav'),'-af','volume=12dB','-c:v','libx264','-crf','18','-preset','fast','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart','-shortest',str(out)],stdin=subprocess.PIPE)
  for i in range(360):
   p.stdin.write(frame(i/24).tobytes())
   if i%48==0:print(i,flush=True)
  p.stdin.close();assert p.wait()==0;print(hashlib.sha256(out.read_bytes()).hexdigest())

