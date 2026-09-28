import { detectKits, Tracker } from '../core/tracker';
const tracker=new Tracker();
self.onmessage=(event:MessageEvent<{data:Uint8ClampedArray;width:number;height:number;time:number}>)=>{
 const {data,width,height,time}=event.data;
 self.postMessage({time,players:tracker.update(detectKits(data,width,height),time),ball:null});
};
