package app.hangar.prototype;

import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.Typeface;
import android.graphics.drawable.Drawable;
import android.view.View;
import com.chaquo.python.PyObject;
import java.util.Locale;

/** Match Console vitals use the same pip pitch for both resources. */
final class UnitVitals extends View {
    private final Drawable heart, bolt;
    private final Paint ink=new Paint(Paint.ANTI_ALIAS_FLAG);
    private final boolean detail;
    private int hp, maximum=1, energy;
    private boolean deployed;
    private String hpLabel="", energyLabel="", slot="";

    UnitVitals(TabletActivity host,boolean detail){
        super(host);this.detail=detail;
        heart=ConsoleSkin.art(host,"unit-tokens/hp.png");
        bolt=ConsoleSkin.art(host,"unit-tokens/energy.png");
        ink.setTypeface(Typeface.MONOSPACE);
        setBackgroundColor(ConsoleSkin.WELL);
        if(!detail)setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO);
    }
    void show(PyObject unit){
        hp=unit.get("hp").toInt();maximum=unit.get("card").get("hp").toInt();energy=unit.get("energy").toInt();
        deployed=unit.get("deployed").toBoolean();
        hpLabel=hp+"/"+maximum;energyLabel=String.valueOf(energy);
        slot=String.format(Locale.ROOT,"%02d",unit.get("slot").toInt());
        heart.setAlpha(detail||deployed?255:155);bolt.setAlpha(detail||deployed?255:155);
        if(detail)setContentDescription("HP "+hpLabel+" · Energy "+energyLabel+" · "+(deployed?"Deployed":"Reserve"));
        invalidate();
    }
    @Override protected void onDraw(Canvas canvas){
        float density=getResources().getDisplayMetrics().density;
        canvas.save();canvas.scale(density,density);
        float width=getWidth()/density, cy=getHeight()/(2*density);
        int segments=detail?10:8;
        int icon=width<240?14:17;
        ink.setTextSize(width<240?10:11);
        String state=deployed?"DEPLOYED":"RESERVE";
        float slotWidth=detail?0:ink.measureText(slot)+6;
        float numbers=ink.measureText(hpLabel)+ink.measureText(energyLabel);
        float fixed=12+slotWidth+2*(icon+3)+numbers+15;
        if(width-fixed-ink.measureText(state)<(segments+5)*3+6)state=deployed?"DEP":"RSV";
        if(width-fixed-ink.measureText(state)<(segments+5)*2+6)state="";
        float stateWidth=state.isEmpty()?0:ink.measureText(state)+6;
        float pitch=Math.max(0,Math.min(16,(width-fixed-stateWidth)/(segments+5)));
        float x=Math.max(4,(width-(fixed-8+stateWidth+pitch*(segments+5)))/2);
        float baseline=cy-(ink.ascent()+ink.descent())/2;
        ink.setColor(ConsoleSkin.INK);
        if(!detail){canvas.drawText(slot,x,baseline,ink);x+=slotWidth;}
        x=resource(canvas,heart,x,cy,baseline,icon,segments,pitch,hp/(float)Math.max(1,maximum),hpLabel,
                detail||deployed?0xffff6494:0xffad5872);
        x=resource(canvas,bolt,x,cy,baseline,icon,5,pitch,energy/5f,energyLabel,
                detail||deployed?0xffffb95e:0xffb38a54);
        ink.setColor(0xffc4ccc6);canvas.drawText(state,x,baseline,ink);canvas.restore();
    }
    private float resource(Canvas c,Drawable symbol,float x,float cy,float baseline,int size,int count,float pitch,
                           float fraction,String value,int color){
        int left=Math.round(x),top=Math.round(cy-size/2f);
        symbol.setBounds(left,top,left+size,top+size);symbol.draw(c);x+=size+3;
        float bar=pitch-Math.min(2,pitch/4);
        for(int i=0;i<count;i++,x+=pitch){
            ink.setColor(0xff414d4f);c.drawRect(x,cy-4,x+bar,cy+4,ink);
            float fill=Math.max(0,Math.min(1,count*fraction-i));
            ink.setColor(color);c.drawRect(x,cy-4,x+bar*fill,cy+4,ink);
        }
        x+=2;ink.setColor(ConsoleSkin.INK);c.drawText(value,x,baseline,ink);
        return x+ink.measureText(value)+6;
    }
}
