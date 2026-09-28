import { distance, type Player, type Team } from './model';
export interface Detection { x: number; y: number; team: Team; confidence: number }
export function detectKits(data: Uint8ClampedArray, width: number, height: number): Detection[] {
 const mask = new Uint8Array(width*height), visited = new Uint8Array(width*height), out: Detection[]=[];
 for(let i=0;i<mask.length;i++){ const r=data[i*4],g=data[i*4+1],b=data[i*4+2]; mask[i]=r>85&&r>g*1.4&&r>b*1.3?1:b>70&&b>r*1.3&&b>g*1.12?2:0; }
 for(let start=0;start<mask.length;start++){
  if(!mask[start]||visited[start])continue;
  const team=mask[start], stack=[start]; visited[start]=1; let count=0,sumX=0,sumY=0,minX=width,maxX=0,minY=height,maxY=0;
  while(stack.length){const p=stack.pop()!,x=p%width,y=Math.floor(p/width);count++;sumX+=x;sumY+=y;minX=Math.min(minX,x);maxX=Math.max(maxX,x);minY=Math.min(minY,y);maxY=Math.max(maxY,y);
   for(const q of [x>0?p-1:-1,x<width-1?p+1:-1,p-width,p+width])if(q>=0&&q<mask.length&&!visited[q]&&mask[q]===team){visited[q]=1;stack.push(q);}
  }
  const w=maxX-minX+1,h=maxY-minY+1;
  if(count>=7&&count<width*height*.008&&h>=3&&h>w*.65&&h<w*6&&sumY/count>height*.08)out.push({x:sumX/count/width*100,y:Math.min(100,(maxY+h*.5)/height*100),team:team===1?'home':'away',confidence:.45});
 }
 return out.sort((a,b)=>a.x-b.x).slice(0,30);
}
export class Tracker {
 private tracks: (Player & {seen:number})[]=[]; private nextId=1;
 update(detections:Detection[],time:number):Player[]{
  this.tracks=this.tracks.filter(t=>time-t.seen<.8);
  const used=new Set<number>(), result:Player[]=[];
  for(const d of detections){
   const nearest=this.tracks.filter(t=>t.team===d.team&&!used.has(t.id)&&distance(t,d)<7).sort((a,b)=>distance(a,d)-distance(b,d))[0];
   const track={...d,id:nearest?.id??this.nextId++,seen:time};used.add(track.id);result.push(track);
   if(nearest)Object.assign(nearest,track);else this.tracks.push(track);
  }
  return result;
 }
}
