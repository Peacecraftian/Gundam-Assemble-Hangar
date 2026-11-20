package app.hangar.prototype;

import android.app.Activity;
import android.content.Context;
import android.content.res.ColorStateList;
import android.graphics.*;
import android.graphics.drawable.*;
import android.text.TextUtils;
import android.view.Gravity;
import android.view.View;
import android.widget.*;
import java.io.*;

final class ConsoleSkin {
    static final int INK=0xfff2ede0, EDGE=0xff626e6c, PANEL=0xff242b2d, WELL=0xff191f21,
            AMBER=0xffffb762, CREAM=0xffe2daca;
    static final int[] TEAM={0xff82d6c3,0xffffa18d}, HOUSING={0xff293d3a,0xff41332f};
    static final int COMPACT_FACE_INSET_DP = 8;
    static final String[] TABS={"Mission Sortie","Battlefield","Match Console","Tactics"};
    static final String[] ICONS={"layers","map","sliders-vertical","gallery-vertical-end"};
    private static Typeface display, stencil;
    static int dp(Context c,float n){return Math.round(c.getResources().getDisplayMetrics().density*n);}
    static Typeface font(Context c){if(display==null) display=Typeface.createFromAsset(c.getAssets(),"ChakraPetch-Bold.ttf");return display;}
    static Typeface digits(Context c){if(stencil==null) stencil=Typeface.createFromAsset(c.getAssets(),"SairaStencilOne-Regular.ttf");return stencil;}
    static GradientDrawable plate(Context c,int top,int bottom,int rim) {
        GradientDrawable d=new GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM,new int[]{top,bottom});
        d.setCornerRadius(dp(c,4));d.setStroke(dp(c,1),rim);return d;
    }
    static void panel(View v,int color){v.setBackground(plate(v.getContext(),color,color,EDGE));}
    static void finish(Button b,int top,int bottom,int rim,int ink) {
        finish(b,top,bottom,rim,ink,2);
    }
    private static void finish(Button b,int top,int bottom,int rim,int ink,int verticalInsetDp) {
        Context c=b.getContext();
        StateListDrawable states=new StateListDrawable();
        states.addState(new int[]{-android.R.attr.state_enabled},plate(c,0xff323a3b,0xff293031,0xff475151));
        states.addState(new int[]{android.R.attr.state_pressed},plate(c,bottom,top,AMBER));
        states.addState(new int[]{android.R.attr.state_focused},plate(c,top,bottom,0xffd1edff));
        states.addState(new int[0],plate(c,top,bottom,rim));
        b.setBackgroundTintList(null);
        int gap=dp(c,2);
        int verticalGap=dp(c,verticalInsetDp);
        b.setBackground(new InsetDrawable(states,gap,verticalGap,gap,verticalGap));
        b.setTextColor(new ColorStateList(new int[][]{{-android.R.attr.state_enabled},{}},new int[]{0xffa2aaa5,ink}));
        b.setStateListAnimator(null);b.setElevation(dp(c,1));b.setPadding(dp(c,7),0,dp(c,7),0);
    }
    static Button button(Context c) {
        return button(c,2);
    }
    static Button button(Context c,int verticalInsetDp) {
        Button b=new Button(c);
        b.setAllCaps(false);b.setTypeface(font(c));b.setTextSize(14);b.setMinimumWidth(0);b.setMinWidth(0);
        b.setMinHeight(dp(c,48));b.setMinimumHeight(dp(c,48));
        finish(b,0xff425053,0xff303a3c,EDGE,INK,verticalInsetDp);return b;
    }
    static android.app.AlertDialog.Builder dialog(Context c) {
        return new android.app.AlertDialog.Builder(c){
            @Override public android.app.AlertDialog create(){
                android.app.AlertDialog dialog=super.create();
                dialog.setOnShowListener(ignored->{
                    dialog.getWindow().setBackgroundDrawable(new InsetDrawable(plate(c,PANEL,WELL,EDGE),dp(c,5)));
                    for(int which:new int[]{-1,-2,-3}){
                        Button b=dialog.getButton(which);if(b==null || b.getVisibility()!=View.VISIBLE)continue;
                        b.setAllCaps(false);b.setTypeface(font(c));b.setMinHeight(dp(c,48));b.setMinimumWidth(dp(c,96));
                        if(which==-1)primary(b);else finish(b,0xff425053,0xff303a3c,EDGE,INK);
                    }
                });
                return dialog;
            }
        };
    }
    static Drawable hazard(Context c){
        Drawable marker=new Drawable(){
            final Paint p=new Paint(Paint.ANTI_ALIAS_FLAG);
            public void draw(Canvas cv){Rect b=getBounds();cv.save();cv.clipRect(b);
                p.setStrokeWidth(dp(c,2));p.setColor(0xff523b24);
                for(int x=b.left-b.height();x<b.right;x+=dp(c,6))cv.drawLine(x,b.bottom,x+b.height(),b.top,p);
                cv.restore();}
            public void setAlpha(int a){}public void setColorFilter(ColorFilter f){}
            public int getOpacity(){return android.graphics.PixelFormat.TRANSLUCENT;}
        };
        marker.setBounds(0,0,dp(c,22),dp(c,14));return marker;
    }
    static void primary(Button b){finish(b,0xffffbe72,0xffed9643,0xffc07d36,0xff24190f);}
    static TextView title(Context c,String text,int size){
        TextView t=new TextView(c);t.setTypeface(font(c));t.setTextColor(INK);t.setTextSize(size);
        t.setText(text);t.setGravity(Gravity.CENTER);t.setSingleLine();t.setEllipsize(TextUtils.TruncateAt.END);return t;
    }
    private static final java.util.Map<String,Drawable.ConstantState> artwork=new java.util.HashMap<>();
    static Drawable art(Context c,String file) {
        Drawable.ConstantState cached=artwork.get(file);
        if(cached!=null)return cached.newDrawable().mutate();
        try(InputStream in=c.getAssets().open(file)){
            Drawable picture=Drawable.createFromStream(in,file);
            if(picture.getConstantState()!=null)artwork.put(file,picture.getConstantState());
            return picture.mutate();
        }
        catch(IOException e){throw new IllegalStateException(file,e);}
    }
    static void background(View v){
        final Context c=v.getContext();
        v.setBackground(new Drawable(){
            final Paint paint=new Paint(); Shader glow;
            protected void onBoundsChange(Rect r){if(r.width()>0)glow=new RadialGradient(r.centerX(),r.top,r.width()*.8f,0xff252f32,0xff151a1c,Shader.TileMode.CLAMP);}
            public void draw(Canvas cv){Rect r=getBounds();paint.setColor(-1);paint.setShader(glow);cv.drawRect(r,paint);
                paint.setShader(null);paint.setColor(0x0c8eaaa7);int step=dp(c,32);
                for(int x=0;x<r.right;x+=step)cv.drawLine(x,0,x,r.bottom,paint);
                for(int y=0;y<r.bottom;y+=step)cv.drawLine(0,y,r.right,y,paint);}
            public void setAlpha(int a){} public void setColorFilter(ColorFilter f){}
            public int getOpacity(){return android.graphics.PixelFormat.OPAQUE;}
        });
    }
    interface Navigate {void open(int tab);}
    static View header(Activity c,int active,boolean match,Navigate route) {
        LinearLayout bar=new LinearLayout(c); bar.setGravity(Gravity.CENTER_VERTICAL);
        bar.setBackground(plate(c,0xfff1eadb,0xffd8cfbd,0xffa59f92));bar.setElevation(dp(c,3));
        bar.addView(screw(c,false),dp(c,40),dp(c,48));
        ImageView logo=new ImageView(c);logo.setImageDrawable(art(c,"console/gundam-assemble-hangar.png"));
        logo.setScaleType(ImageView.ScaleType.FIT_START);logo.setAdjustViewBounds(true);
        LinearLayout.LayoutParams wing=new LinearLayout.LayoutParams(0,dp(c,33),1);
        bar.addView(logo,wing);
        // Inset the artwork while keeping the entire 48dp navigation row tappable.
        LinearLayout rail=new LinearLayout(c);
        int railInset=dp(c,5);
        rail.setBackground(new InsetDrawable(plate(c,WELL,WELL,EDGE),0,railInset,0,railInset));
        rail.setPadding(0,0,0,0);
        bar.addView(rail);
        boolean compact=c.getResources().getConfiguration().screenWidthDp<900;
        for(int i=0;i<TABS.length;i++){
            final int dest=i;boolean here=i==active;
            Button tab=button(c);tab.setText(TABS[i]);tab.setTextSize(compact?12:13);
            tab.setSingleLine();tab.setSelected(here);tab.setEnabled(i!=2||match);
            Drawable glyph=art(c,"console/"+ICONS[i]+".png").mutate();glyph.setTint(here?AMBER:INK);
            glyph.setBounds(0,0,dp(c,14),dp(c,14));tab.setCompoundDrawables(glyph,null,null,null);
            tab.setCompoundDrawablePadding(dp(c,5));
            finish(tab,here?0xff493521:PANEL,here?0xff664a30:PANEL,here?0xffce914c:PANEL,here?0xffffdfb4:INK,COMPACT_FACE_INSET_DP);
            tab.setOnClickListener(v->{if(!here)route.open(dest);});
            rail.addView(tab,-2,dp(c,48));
        }
        LinearLayout trim=new LinearLayout(c);trim.setGravity(Gravity.RIGHT|Gravity.CENTER_VERTICAL);bar.addView(trim,wing);
        View led=new View(c);led.setBackground(plate(c,0xffb3df86,0xff8bb65d,0xff80916b));trim.addView(led,dp(c,11),dp(c,11));
        ImageView speaker=new ImageView(c);speaker.setPadding(dp(c,5),0,0,0);
        speaker.setImageDrawable(art(c,"console/speaker-grille.png"));trim.addView(speaker,dp(c,65),dp(c,23));
        bar.addView(screw(c,true),dp(c,40),dp(c,48));return bar;
    }
    private static View screw(Activity c,boolean right){
        Button b=button(c);b.setPadding(0,0,0,0);b.setElevation(0);
        b.setBackground(new Drawable(){
            final Paint p=new Paint(Paint.ANTI_ALIAS_FLAG);
            public void draw(Canvas canvas){
                float x=getBounds().exactCenterX(),y=getBounds().exactCenterY(),r=dp(c,8);
                p.setColor(0xffb6ad9b);canvas.drawCircle(x,y,r,p);p.setColor(0xffe9e2d2);
                canvas.drawArc(x-r,y-r,x+r,y+r,25,150,false,p);
                canvas.save();canvas.rotate(right?-49:-34,x,y);p.setStrokeWidth(dp(c,2));
                p.setColor(0xff857c6a);canvas.drawLine(x-r+2,y,x+r-2,y,p);canvas.restore();
            }
            public void setAlpha(int a){}public void setColorFilter(ColorFilter f){}
            public int getOpacity(){return android.graphics.PixelFormat.TRANSLUCENT;}
        });
        b.setContentDescription("Toggle fullscreen, "+(right?"right":"left")+" screw");
        b.setOnClickListener(v->TabletDisplay.toggle(c));return b;
    }
}
