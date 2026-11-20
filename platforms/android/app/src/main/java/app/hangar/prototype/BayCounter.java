package app.hangar.prototype;

import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.Typeface;
import android.graphics.drawable.Drawable;
import android.text.Editable;
import android.text.InputType;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.widget.*;

// Keep the editable number authoritative, including when the visual meter is full.
final class BayCounter extends LinearLayout {
    private final EditText field;
    private final int maximum;
    private final Button minus, plus;
    private final boolean editable;
    private Meter meter;

    BayCounter(TabletActivity host,String name,String icon,int initial,int maximum,int segments,int color,
               boolean editable,Runnable changed) {
        super(host);
        this.maximum=maximum;this.editable=editable;
        setOrientation(VERTICAL);
        LinearLayout heading=new LinearLayout(host);
        heading.setGravity(Gravity.CENTER_VERTICAL);
        addView(heading);
        TextView caption=ConsoleSkin.title(host,name.equals("HP")?"HP / "+maximum:name,14);
        caption.setGravity(Gravity.START|Gravity.CENTER_VERTICAL);
        if(segments>0){
            Drawable symbol=ConsoleSkin.art(host,"unit-tokens/"+icon+".png");
            symbol.setBounds(0,0,host.dp(22),host.dp(22));
            caption.setCompoundDrawables(symbol,null,null,null);caption.setCompoundDrawablePadding(host.dp(5));
        }
        heading.addView(caption,new LayoutParams(0,-2,1));
        field=new EditText(host);field.setSingleLine(true);field.setSelectAllOnFocus(true);
        field.setGravity(Gravity.CENTER);field.setTypeface(Typeface.MONOSPACE);
        field.setInputType(InputType.TYPE_CLASS_NUMBER);field.setTextSize(15);
        field.setText(String.valueOf(initial));field.setContentDescription(name);field.setEnabled(editable);
        if(segments>0)heading.addView(field,host.dp(70),host.dp(44));
        else caption.setGravity(Gravity.CENTER);
        LinearLayout row=new LinearLayout(host);row.setGravity(Gravity.CENTER);addView(row);
        minus=step(host,row,name,-1,segments==0);
        if(segments>0){
            meter=new Meter(host,segments,color);
            LayoutParams p=new LayoutParams(0,host.dp(12),1);p.setMargins(host.dp(5),0,host.dp(5),0);
            row.addView(meter,p);
        } else {
            LinearLayout dial=new LinearLayout(host);dial.setOrientation(VERTICAL);dial.setGravity(Gravity.CENTER);
            int inset=host.dp(2);
            dial.setBackground(new android.graphics.drawable.InsetDrawable(
                    ConsoleSkin.plate(host,ConsoleSkin.PANEL,ConsoleSkin.WELL,ConsoleSkin.EDGE),inset));
            dial.setPadding(inset,inset,inset,inset);
            // Each counter spans half the upgrades panel. Two fifths of that matches one of five Shield slots.
            row.addView(dial,new LayoutParams(0,host.dp(ServiceBay.UPGRADE_TILE_HEIGHT_DP),4));
            ImageButton token=new ImageButton(host);token.setPadding(0,0,0,0);
            token.setScaleType(ImageView.ScaleType.CENTER);token.setBackgroundColor(0);
            token.setImageDrawable(ServiceBay.upgradeIcon(host,icon));token.setContentDescription("Add "+name+" upgrade");
            token.setOnClickListener(v->adjust(1));token.setEnabled(editable);dial.addView(token,-1,host.dp(38));
            field.setBackground(null);field.setIncludeFontPadding(false);field.setTextSize(13);
            field.setPadding(0,0,0,host.dp(1));
            dial.addView(field,new LayoutParams(-1,0,1));
        }
        plus=step(host,row,name,1,segments==0);
        field.addTextChangedListener(new TextWatcher(){
            public void beforeTextChanged(CharSequence s,int start,int count,int after){}
            public void onTextChanged(CharSequence s,int start,int before,int count){refresh(segments);changed.run();}
            public void afterTextChanged(Editable e){}
        });
        refresh(segments);
    }
    private Button step(TabletActivity host,LinearLayout row,String name,int delta,boolean upgrade){
        Button b=ConsoleSkin.button(host);b.setText(delta<0?"−":"+");b.setTextSize(21);
        b.setContentDescription((delta<0?"Decrease ":"Increase ")+name);
        b.setOnClickListener(v->adjust(delta));
        if(upgrade){
            FrameLayout side=new FrameLayout(host);row.addView(side,new LayoutParams(0,host.dp(48),3));
            b.setWidth(host.dp(48));
            side.addView(b,new FrameLayout.LayoutParams(LayoutParams.WRAP_CONTENT,-1,delta<0?Gravity.END:Gravity.START));
        }else row.addView(b,host.dp(48),host.dp(48));
        return b;
    }
    boolean positive(){int n=parsed();return n>0 && n<=maximum;}
    private int parsed(){
        try{return Integer.parseInt(raw());}catch(NumberFormatException e){return -1;}
    }
    void restore(String text){field.setText(text);}
    String raw(){return field.getText().toString();}
    int value(){
        int n=parsed();
        if(n>=0 && n<=maximum)return n;
        field.requestFocus();
        throw new IllegalArgumentException("Check "+field.getContentDescription()+" (0–"+maximum+").");
    }
    private void adjust(int delta){
        int n=parsed();if(n>=0 && n<=maximum)field.setText(String.valueOf(Math.max(0,Math.min((long)maximum,(long)n+delta))));
    }
    private void refresh(int segments){
        int n=parsed();
        minus.setEnabled(editable && n>0 && n<=maximum);plus.setEnabled(editable && n>=0 && n<maximum);
        if(meter!=null){
            meter.filled=maximum==Integer.MAX_VALUE ? Math.max(0,Math.min(n,segments)):
                    Math.round(Math.max(0,Math.min(n,maximum))/(float)maximum*segments);
            meter.invalidate();
        }
    }
    private static final class Meter extends View{
        final Paint paint=new Paint();final int segments,color;int filled;
        Meter(TabletActivity host,int segments,int color){super(host);this.segments=segments;this.color=color;}
        @Override protected void onDraw(Canvas c){
            float pitch=getWidth()/(float)segments;
            float gap=Math.min(pitch*.2f,getResources().getDisplayMetrics().density*2);
            for(int i=0;i<segments;i++){
                paint.setColor(i<filled?color:0xff455153);
                c.drawRect(i*pitch,0,(i+1)*pitch-gap,getHeight(),paint);
            }
        }
    }
}
