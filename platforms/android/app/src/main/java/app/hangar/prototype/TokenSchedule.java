package app.hangar.prototype;

import android.graphics.Typeface;
import android.widget.*;
import com.chaquo.python.PyObject;
import java.util.List;

// Rebuild the stack slots whenever the destination changes. All controls edit the dialog draft.
final class TokenSchedule {
    private final TabletActivity host;
    private final LinearLayout body;
    private final boolean editable, inline;
    private final Runnable changed;
    private final int id,side;
    private int phase,round,position;
    private final LinearLayout slots;
    private LinearLayout phases,rounds;
    private NumberPicker phaseWheel;
    TokenSchedule(ConsoleForm form,PyObject unit) {
        this(form.host,form.body,unit,true,false,()->{});
    }
    TokenSchedule(TabletActivity host,LinearLayout body,PyObject unit,boolean editable,boolean inline,Runnable changed){
        this.host=host;this.body=body;this.editable=editable;this.inline=inline;this.changed=changed;
        id=unit.get("id").toInt(); side=unit.get("player").toInt();
        phase=unit.get("phase").toInt();round=unit.get("round").toInt();
        int horizon=Math.max(phase,host.match().get("phases").toInt());
        int last=horizon==Integer.MAX_VALUE?horizon:horizon+1;
        LinearLayout phaseBox=group("Scheduled Phase");
        if(last>12){
            NumberPicker wheel=new NumberPicker(host);phaseWheel=wheel;
            wheel.setMinValue(1);wheel.setMaxValue(last);wheel.setValue(phase);wheel.setWrapSelectorWheel(false);
            wheel.setContentDescription("Scheduled Phase");
            wheel.setEnabled(editable);phaseBox.addView(wheel);
            wheel.setOnValueChangedListener((v,old,next)->{phase=next;resetPosition();changed.run();});
        } else {phases=strip(phaseBox);choices(phases,"Phase",last,phase,n->{phase=n;resetPosition();});}
        rounds=strip(group("Scheduled round"));
        choices(rounds,"Round",10,round,n->{round=n;resetPosition();});
        slots=strip(group("Stack position"));resetPosition();
    }
    private LinearLayout group(String title){
        LinearLayout group=new LinearLayout(host);group.setGravity(android.view.Gravity.CENTER_VERTICAL);
        if(!inline)group.setOrientation(LinearLayout.VERTICAL);
        TextView label=ConsoleSkin.title(host,title,14);label.setGravity(android.view.Gravity.START|android.view.Gravity.CENTER_VERTICAL);
        group.addView(label,inline?host.dp(120):-1,-2);body.addView(group);return group;
    }
    private LinearLayout strip(LinearLayout group) {
        HorizontalScrollView scroll=new HorizontalScrollView(host);
        LinearLayout row=new LinearLayout(host);scroll.addView(row);group.addView(scroll);return row;
    }
    private interface Pick{void select(int i);}
    private void choices(LinearLayout row,String name,int count,int selected,Pick pick) {
        row.removeAllViews();
        for(int i=1;i<=count;i++){
            final int value=i;Button b=ConsoleSkin.button(host);b.setText(String.valueOf(i));
            b.setContentDescription(name+" "+i);b.setTypeface(Typeface.MONOSPACE);
            b.setEnabled(editable);mark(b,i==selected);row.addView(b,host.dp(48),host.dp(48));
            b.setOnClickListener(v->{for(int k=0;k<row.getChildCount();k++)mark((Button)row.getChildAt(k),k+1==value);pick.select(value);changed.run();});
        }
    }
    private void mark(Button b,boolean on) {
        b.setSelected(on);
        ConsoleSkin.finish(b,on?0xff715335:0xff404c4e,on?0xff493521:ConsoleSkin.WELL,on?ConsoleSkin.AMBER:ConsoleSkin.EDGE,ConsoleSkin.INK);
    }
    private void resetPosition() {
        List<PyObject> tokens=host.match().callAttr("tokens",side,phase,round).asList();
        int count=tokens.size()+1;position=count;
        for(int i=0;i<tokens.size();i++) if(tokens.get(i).get("id").toInt()==id){count--;position=i+1;break;}
        choices(slots,"Stack position",count,position,n->position=n);
    }
    void restore(int p,int r,int rank){
        if(p!=phase){
            if(phaseWheel!=null){phaseWheel.setValue(p);phase=phaseWheel.getValue();resetPosition();}
            else phases.getChildAt(p-1).performClick();
        }
        if(r!=round)rounds.getChildAt(r-1).performClick();
        if(rank!=position)slots.getChildAt(rank-1).performClick();
    }
    int[] values(){return new int[]{phase,round,position};}
}
