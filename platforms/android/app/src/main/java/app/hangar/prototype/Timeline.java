package app.hangar.prototype;

import android.content.Context;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.Drawable;
import android.view.DragEvent;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewConfiguration;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.ScrollView;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.text.TextUtils;
import java.util.Locale;
import java.util.List;
import java.util.HashMap;
import com.chaquo.python.PyObject;

final class Timeline extends LinearLayout {
    interface Actions {
        void select(int id);
        void inspect(int id);
        void schedule();
        void otherPhases();
        void move(int id, int round, int position);
    }

    private static final int ROUNDS = 10;
    private static final int[] ACCENTS = {0xff77d6c1, 0xffff9b88};
    private static final int CELL = 0xff242c2e, TARGET = 0xff946637;
    private int currentRound=1;
    private final LinearLayout[][] cells = new LinearLayout[2][ROUNDS];
    private final HashMap<Integer,Integer> owners = new HashMap<>();
    private final Button scheduleLink, otherPhases;
    private final TextView[] rounds = new TextView[ROUNDS];
    private int lastId=-1;
    private long lastTap;
    private final Actions actions;
    private final Typeface font;

    Timeline(Context context, Typeface font, List<PyObject> players, Actions actions) {
        super(context);
        this.font = font;
        this.actions = actions;
        setOrientation(VERTICAL);
        setPadding(dp(3),dp(3),dp(3),dp(3));
        LinearLayout header = row();
        scheduleLink = headerLink(header, "Timeline", actions::schedule);
        otherPhases = headerLink(header, "Other phases", actions::otherPhases);

        LinearLayout roundLabels = row();
        heading(roundLabels, "Round", ConsoleSkin.INK);
        for (int n = 1; n <= ROUNDS; n++) {
            TextView number = text();
            number.setText(String.valueOf(n));
            rounds[n-1]=number;
            roundLabels.addView(number, slot(22));
        }
        for (int side = 0; side < cells.length; side++) {
            final int owner = side;
            LinearLayout lane = row();
            LinearLayout player = new LinearLayout(context);
            player.setOrientation(VERTICAL);
            lane.addView(player, dp(68), LayoutParams.WRAP_CONTENT);
            heading(player, players.get(side).toString(), ACCENTS[side]);
            player.setGravity(Gravity.CENTER);
            player.setBackgroundColor(ConsoleSkin.HOUSING[side]);
            for (int round = 1; round <= ROUNDS; round++) {
                final int destination = round;
                ScrollView cell = new ScrollView(context){
                    final Drawable decal=ConsoleSkin.art(context,"console/pixel-decal.png");
                    @Override protected void onDraw(android.graphics.Canvas cv) {
                        super.onDraw(cv);
                        if(cells[owner][destination-1].getChildCount()!=0)return;
                        int x=getWidth()/2,y=getHeight()/2;
                        decal.setAlpha(46);decal.setBounds(x-dp(14),y-dp(10),x+dp(14),y+dp(10));decal.draw(cv);
                    }
                };
                cell.setWillNotDraw(false);
                cell.setFillViewport(true);
                paintCell(cell,destination,false);
                lane.addView(cell, slot(52));
                TokenStack stack = new TokenStack(context);
                stack.setOrientation(VERTICAL);
                cells[side][round - 1] = stack;
                cell.addView(stack);
                cell.setOnDragListener((v, event) -> {
                    if (!Integer.valueOf(owner).equals(owners.get(event.getLocalState()))) return false;
                    switch (event.getAction()) {
                        case DragEvent.ACTION_DRAG_ENTERED: paintCell(cell,destination,true); break;
                        case DragEvent.ACTION_DRAG_LOCATION:
                            float pointer=event.getY();
                            if(pointer<dp(12))cell.scrollBy(0,-dp(5));
                            else if(pointer>cell.getHeight()-dp(12))cell.scrollBy(0,dp(5));
                            stack.insertion((Integer)event.getLocalState(),pointer+cell.getScrollY(),true);
                            break;
                        case DragEvent.ACTION_DRAG_ENDED:
                            for(int k=0;k<stack.getChildCount();k++)stack.getChildAt(k).setAlpha(1);
                        case DragEvent.ACTION_DRAG_EXITED:
                            stack.clearMarker();paintCell(cell,destination,false);break;
                        case DragEvent.ACTION_DROP:
                            int id=(Integer)event.getLocalState();
                            float y=event.getY()+cell.getScrollY();
                            stack.clearMarker();
                            actions.move(id,destination,stack.insertion(id,y,false));
                            break;
                    }
                    return true;
                });
            }
        }
    }


    private final class TokenStack extends LinearLayout {
        private final android.graphics.Paint marker=new android.graphics.Paint();
        private int markerY=-1;
        TokenStack(Context context){super(context);marker.setColor(ConsoleSkin.AMBER);}
        void clearMarker(){if(markerY>=0){markerY=-1;invalidate();}}
        int insertion(int movingId,float pointerY,boolean preview){
            int position=1,line=0;
            for(int i=0;i<getChildCount();i++){
                View ally=getChildAt(i);
                if(Integer.valueOf(movingId).equals(ally.getTag()))continue;
                if(pointerY<=ally.getTop()+ally.getHeight()/2f){line=ally.getTop();break;}
                position++;line=ally.getBottom();
            }
            if(preview && markerY!=line){markerY=line;invalidate();}
            return position;
        }
        @Override protected void dispatchDraw(android.graphics.Canvas canvas){
            super.dispatchDraw(canvas);
            if(markerY<0)return;
            int y=Math.max(0,Math.min(getHeight()-dp(3),markerY-dp(1)));
            canvas.drawRect(dp(2),y,getWidth()-dp(2),y+dp(3),marker);
        }
    }

    void showUnits(List<PyObject> units,int currentPhase,int currentRound) {
        this.currentRound=currentRound;
        for(LinearLayout[] lane:cells) for(int i=0;i<ROUNDS;i++) paintCell((ScrollView)lane[i].getParent(),i+1,false);
        for (int i=0;i<ROUNDS;i++) rounds[i].setBackgroundColor(i+1==currentRound ? TARGET : Color.TRANSPARENT);
        for (LinearLayout[] lane : cells) for (LinearLayout cell : lane) cell.removeAllViews();
        owners.clear();
        java.util.ArrayList<PyObject> ordered = new java.util.ArrayList<>(units);
        ordered.sort(java.util.Comparator.comparingInt(u -> u.get("stack").toInt()));
        int[][] counts=new int[2][ROUNDS];
        int offPhase = 0;
        for (PyObject unit : ordered) {
            if (unit.get("phase").toInt() == currentPhase) {
                counts[unit.get("player").toInt()][unit.get("round").toInt()-1]++;
            } else {
                offPhase++;
            }
        }
        otherPhases.setText("Other phases (" + offPhase + ")");
        setLinkEnabled(otherPhases, offPhase > 0);
        for(int side=0;side<2;side++){
            int visible=1;
            for(int n:counts[side])visible=Math.max(visible,Math.min(n,3));
            int laneHeight=visible*44+4;
            for(LinearLayout stack:cells[side]){
                View cell=(View)stack.getParent();LayoutParams p=(LayoutParams)cell.getLayoutParams();
                if(p.height!=dp(laneHeight)){p.height=dp(laneHeight);cell.setLayoutParams(p);}
            }
        }
        for (PyObject unit : ordered) {
            int id = unit.get("id").toInt(), side = unit.get("player").toInt();
            int round = unit.get("round").toInt(), phase = unit.get("phase").toInt();
            if (phase!=currentPhase) continue;
            owners.put(id, side);
            boolean dense=counts[side][round-1]>=4;
            FrameLayout token=new FrameLayout(getContext());
            token.setTag(id);token.setFocusable(true);
            String label=unit.get("label").toString();
            token.setContentDescription(label+", phase "+phase+", round "+round);
            LinearLayout strip=new LinearLayout(getContext());
            strip.setGravity(Gravity.CENTER_VERTICAL);strip.setPadding(dp(1),dp(1),dp(2),dp(1));
            strip.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS);
            token.addView(strip,new FrameLayout.LayoutParams(-1,dp(dense?24:30),Gravity.CENTER));
            ImageView face=new ImageView(getContext());
            String number=unit.get("card").get("number").toString();
            face.setImageDrawable(ConsoleSkin.art(getContext(),"portraits/"+number+".webp"));
            face.setScaleType(ImageView.ScaleType.CENTER_CROP);
            boolean narrow=getResources().getConfiguration().screenWidthDp<1000;
            strip.addView(face,dp(dense||narrow?21:28),-1);
            TextView badge=text();badge.setTypeface(ConsoleSkin.digits(getContext()));
            badge.setText(String.format(Locale.ROOT,"%02d",unit.get("slot").toInt()));
            badge.setTextSize(dense?11:13);badge.setTextColor(ConsoleSkin.WELL);badge.setBackgroundColor(ACCENTS[side]);
            badge.setIncludeFontPadding(false);strip.addView(badge,dp(dense||narrow?16:18),-1);
            TextView name=text();name.setSingleLine();name.setEllipsize(TextUtils.TruncateAt.END);
            name.setTextSize(dense||narrow?11:12);name.setTextColor(ConsoleSkin.INK);
            name.setGravity(Gravity.START|Gravity.CENTER_VERTICAL);name.setPadding(dp(3),0,0,0);
            String printed=unit.get("card").get("name").toString();
            name.setText(printed);strip.addView(name,new LayoutParams(0,-1,1));
            name.addOnLayoutChangeListener((v,l,top,r,bottom,ol,ot,or,ob)->{
                if(r-l==or-ol)return;
                int room=Math.max(0,r-l-name.getPaddingLeft()-dp(1));
                name.setTextScaleX(1f);
                String fit=name.getPaint().measureText(printed)*.82f<=room?printed:printed.replaceFirst(" \\(EW\\)$","").replaceFirst("^Gundam ","");
                float width=name.getPaint().measureText(fit);
                name.setTextScaleX(Math.max(.82f,Math.min(1f,room/Math.max(1f,width))));
                if(!name.getText().toString().equals(fit))name.setText(fit);
            });
            token.setOnClickListener(v -> {
                long now=android.os.SystemClock.uptimeMillis();
                if(id==lastId && now-lastTap<ViewConfiguration.getDoubleTapTimeout()){lastId=-1;actions.inspect(id);}
                else {lastId=id;lastTap=now;actions.select(id);}
            });
            token.setOnTouchListener(new TokenTouch(id));
            cells[side][round - 1].addView(token,LayoutParams.MATCH_PARENT,dp(44));
        }
    }

    void highlight(int id) {
        for(int side=0;side<2;side++)for(LinearLayout stack:cells[side])for(int i=0;i<stack.getChildCount();i++){
            View v=stack.getChildAt(i);boolean on=Integer.valueOf(id).equals(v.getTag());v.setSelected(on);
            ((FrameLayout)v).getChildAt(0).setBackground(ConsoleSkin.plate(getContext(),ConsoleSkin.HOUSING[side],CELL,on?ConsoleSkin.AMBER:ACCENTS[side]));
        }
    }
    private Button headerLink(LinearLayout header, String label, Runnable action) {
        Button link = new Button(getContext(), null, android.R.attr.borderlessButtonStyle);
        link.setText(label);
        link.setAllCaps(false);
        link.setTypeface(font);
        link.setTextSize(14);
        link.setSingleLine();
        link.setIncludeFontPadding(false);
        link.setMinWidth(dp(48));
        link.setMinHeight(dp(32));
        link.setMinimumHeight(dp(32));
        link.setPadding(dp(6), dp(2), dp(6), dp(2));
        link.setOnClickListener(v -> action.run());
        header.addView(link, LayoutParams.WRAP_CONTENT, LayoutParams.WRAP_CONTENT);
        return link;
    }

    private void setLinkEnabled(Button link, boolean enabled) {
        link.setEnabled(enabled);
        link.setTextColor(enabled ? ConsoleSkin.AMBER : ConsoleSkin.INK);
        link.setAlpha(enabled ? 1f : .65f);
        int underline = android.graphics.Paint.UNDERLINE_TEXT_FLAG;
        int flags = link.getPaintFlags();
        link.setPaintFlags(enabled ? flags | underline : flags & ~underline);
    }

    void updateScheduleLink(boolean editable,String unitLabel){
        setLinkEnabled(scheduleLink, editable);
        String action="Schedule "+unitLabel+" on the Timeline";
        scheduleLink.setContentDescription(editable?action:"Timeline");
        if(android.os.Build.VERSION.SDK_INT>=26)scheduleLink.setTooltipText(editable?action:null);
    }
    private void paintCell(ScrollView view,int round,boolean target) {
        boolean current=round==currentRound;
        int fill=target?TARGET:current?0xff392f25:round%2==0?CELL:ConsoleSkin.WELL;
        view.setBackground(ConsoleSkin.plate(getContext(),fill,fill,target||current?ConsoleSkin.AMBER:0xff4d5656));
    }
    private final class TokenTouch implements OnTouchListener {
        private final int id;
        private float downX, downY;
        TokenTouch(int id) { this.id = id; }
        public boolean onTouch(View v, MotionEvent event) {
            switch (event.getActionMasked()) {
                case MotionEvent.ACTION_DOWN:
                    downX = event.getX(); downY = event.getY(); return true;
                case MotionEvent.ACTION_MOVE:
                    if (Math.hypot(event.getX() - downX, event.getY() - downY)
                            > ViewConfiguration.get(getContext()).getScaledTouchSlop()) {
                        if(v.startDragAndDrop(null,new View.DragShadowBuilder(v){
                            @Override public void onDrawShadow(android.graphics.Canvas canvas){
                                canvas.save();canvas.scale(.92f,.92f,v.getWidth()/2f,v.getHeight()/2f);
                                canvas.rotate(-4,v.getWidth()/2f,v.getHeight()/2f);super.onDrawShadow(canvas);canvas.restore();
                            }
                        },id,0)) v.setAlpha(.45f);
                    }
                    return true;
                case MotionEvent.ACTION_UP: v.performClick(); return true;
                case MotionEvent.ACTION_CANCEL: return true;
                default: return false;
            }
        }
    }

    private int dp(int value) { return Math.round(getResources().getDisplayMetrics().density * value); }
    private LayoutParams slot(int height) {
        LayoutParams p = new LayoutParams(0, dp(height), 1);
        p.setMargins(dp(1), dp(1), dp(1), dp(1));
        return p;
    }
    private LinearLayout row() {
        LinearLayout r = new LinearLayout(getContext());
        r.setGravity(Gravity.CENTER_VERTICAL);
        addView(r);
        return r;
    }
    private TextView text() {
        TextView t = new TextView(getContext());
        t.setTypeface(font);
        t.setGravity(Gravity.CENTER);
        t.setTextSize(14);
        return t;
    }
    private void heading(LinearLayout row, String label, int color) {
        TextView t = text();
        t.setText(label);
        t.setTextColor(color);
        row.addView(t, dp(68), LayoutParams.WRAP_CONTENT);
    }
}
