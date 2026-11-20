package app.hangar.prototype;

import android.app.Dialog;
import android.graphics.BitmapFactory;
import android.graphics.Typeface;
import android.graphics.drawable.Drawable;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import android.widget.*;
import com.chaquo.python.PyObject;
import org.json.*;
import java.io.*;
import java.util.List;
import java.util.Locale;

final class ServiceBay extends Dialog {
    private static final int MATCH=-1, WRAP=-2;
    static final int UPGRADE_TILE_HEIGHT_DP=64;
    private static final String[] CONDITIONS={"Disarm","Fracture","Slow"};
    private static final String[] CONDITION_ART={"disarmed-status","fractured-status","slow-status"};
    private static final String[] SHIELDS={"empty","active","spent"};
    private static final String[] SHIELD_LABELS={"Empty","Active","Inactive"};
    private final TabletActivity host;
    private final ConsoleMenus menus;
    private final PyObject unit,card;
    private final int id,side;
    private final boolean editable,wasDeployed;
    private boolean deployed;
    private final int[] shield=new int[5];
    private final CheckBox[] conditions=new CheckBox[3];
    private CheckBox keepOld;
    private final java.util.LinkedHashSet<String> launchSystems=new java.util.LinkedHashSet<>();
    private final java.util.ArrayList<Runnable> systemReadouts=new java.util.ArrayList<>();
    private BayCounter hp,energy,strength,speed;
    private TokenSchedule schedule;
    private EditText note;
    private final Runnable[] paintShields=new Runnable[5];
    private ScrollView scroll;
    private TextView notice;
    private Button deploy,reserve;
    private String original;

    ServiceBay(TabletActivity host, ConsoleMenus menus){
        super(host,android.R.style.Theme_Material_NoActionBar);
        this.host=host;this.menus=menus;unit=host.unit();card=unit.get("card");
        id=unit.get("id").toInt();side=unit.get("player").toInt();editable=host.active();
        deployed=wasDeployed=unit.get("deployed").toBoolean();
        LinearLayout page=column(); ConsoleSkin.background(page);
        page.setFocusableInTouchMode(true);page.setFitsSystemWindows(true);page.setPadding(dp(10),dp(6),dp(10),dp(6));
        setContentView(page);
        getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE|WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_HIDDEN);
        LinearLayout header=line(page);header.setBackground(ConsoleSkin.plate(host,0xfff1eadb,ConsoleSkin.CREAM,0xffa59f92));
        ImageView logo=new ImageView(host);logo.setImageDrawable(ConsoleSkin.art(host,"console/gundam-assemble-hangar.png"));
        logo.setScaleType(ImageView.ScaleType.FIT_CENTER);header.addView(logo,dp(134),dp(42));
        TextView title=ConsoleSkin.title(host,"Service Bay",24);title.setTextColor(ConsoleSkin.WELL);
        header.addView(title,new LinearLayout.LayoutParams(0,WRAP,1));
        deploy=button("Deploy",()->deployment(true));header.addView(deploy,dp(124),dp(48));
        LinearLayout tray=new LinearLayout(host);
        LinearLayout.LayoutParams space=new LinearLayout.LayoutParams(MATCH,0,1);space.setMargins(0,dp(6),0,dp(6));page.addView(tray,space);
        LinearLayout inspection=panel("01","Unit Inspection");tray.addView(inspection,weighted(.32f,MATCH));
        inspect(inspection);
        scroll=new ScrollView(host);scroll.setFillViewport(true);
        LinearLayout.LayoutParams right=weighted(.68f,MATCH);right.leftMargin=dp(6);tray.addView(scroll,right);
        LinearLayout controls=column();scroll.addView(controls);
        boolean wide=host.getResources().getConfiguration().screenWidthDp>=980;
        LinearLayout upper=wide?line(controls):controls;
        LinearLayout state=panel("02","Unit State"),upgrades=panel("03","Upgrades");
        if(wide){
            upper.setGravity(Gravity.TOP);upper.addView(state,weighted(.44f,MATCH));
            LinearLayout.LayoutParams up=weighted(.56f,MATCH);up.leftMargin=dp(6);upper.addView(upgrades,up);
        }else {controls.addView(state);controls.addView(upgrades,separated());}
        buildState(state);buildUpgrades(upgrades);
        LinearLayout timing=panel("04","Timeline Token");controls.addView(timing,separated());
        schedule=new TokenSchedule(host,timing,unit,editable,true,this::draftChanged);
        TextView noteTitle=caption("Token notes");timing.addView(noteTitle);
        note=new EditText(host);note.setSingleLine(true);note.setContentDescription("Unit note");
        note.setText(unit.get("note").toString());note.setEnabled(editable);timing.addView(note);
        note.addTextChangedListener(new TextWatcher(){
            public void beforeTextChanged(CharSequence s,int start,int count,int after){}
            public void onTextChanged(CharSequence s,int start,int before,int count){draftChanged();}
            public void afterTextChanged(Editable s){}
        });
        LinearLayout footer=line(page);ConsoleSkin.panel(footer,ConsoleSkin.PANEL);
        notice=caption("");notice.setPadding(dp(10),0,dp(6),0);notice.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
        footer.addView(notice,weighted(1,WRAP));
        footer.addView(button(editable?"Cancel":"Close",this::leave),dp(116),dp(52));
        if(editable){Button save=button("Save unit",this::save);ConsoleSkin.primary(save);footer.addView(save,dp(132),dp(52));}
        original=snapshot();deployment(deployed);
    }

    private int dp(int value){return host.dp(value);}
    private LinearLayout column(){LinearLayout v=new LinearLayout(host);v.setOrientation(LinearLayout.VERTICAL);return v;}
    private LinearLayout line(LinearLayout parent){LinearLayout r=new LinearLayout(host);r.setGravity(Gravity.CENTER_VERTICAL);parent.addView(r);return r;}
    private LinearLayout.LayoutParams weighted(float weight,int height){return new LinearLayout.LayoutParams(0,height,weight);}
    private LinearLayout.LayoutParams separated(){LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(MATCH,WRAP);p.topMargin=dp(6);return p;}
    private Button button(String text,Runnable pressed){Button b=ConsoleSkin.button(host);b.setText(text);b.setOnClickListener(v->pressed.run());return b;}
    private TextView caption(String label){TextView t=new TextView(host);t.setText(label);t.setTextColor(ConsoleSkin.INK);t.setTypeface(ConsoleSkin.font(host));t.setTextSize(14);return t;}
    private LinearLayout panel(String index,String title){
        LinearLayout v=column();ConsoleSkin.panel(v,ConsoleSkin.PANEL);v.setPadding(dp(8),dp(6),dp(8),dp(8));
        LinearLayout heading=line(v);ConsoleSkin.panel(heading,0xff2d3537);
        TextView code=ConsoleSkin.title(host,index,12);code.setTypeface(Typeface.MONOSPACE);code.setTextColor(ConsoleSkin.AMBER);
        heading.addView(code,dp(32),dp(31));heading.addView(caption(title));return v;
    }
    private void inspect(LinearLayout inspection){
        TextView name=caption(card.get("name").toString());name.setTextSize(22);inspection.addView(name);
        TextView owner=caption(String.format(Locale.ROOT,"%s · Player %d / Slot %02d",host.playerName(side),side+1,unit.get("slot").toInt()));
        owner.setTextColor(ConsoleSkin.TEAM[side]);inspection.addView(owner);
        inspection.addView(caption(card.get("title")+" · "+card.get("number")));
        ImageView art=new ImageView(host);art.setScaleType(ImageView.ScaleType.FIT_CENTER);
        art.setBackground(ConsoleSkin.plate(host,ConsoleSkin.WELL,ConsoleSkin.WELL,ConsoleSkin.EDGE));
        art.setPadding(dp(5),dp(5),dp(5),dp(5));art.setContentDescription("Inspect "+card.get("name")+" card");
        try(InputStream in=host.getAssets().open(card.get("image").toString())){art.setImageBitmap(BitmapFactory.decodeStream(in));}
        catch(IOException e){throw new IllegalStateException(e);}
        Runnable enlarge=()->menus.displayCard(card,false);
        art.setOnClickListener(v->enlarge.run());LinearLayout.LayoutParams fill=new LinearLayout.LayoutParams(MATCH,0,1);
        fill.setMargins(0,dp(6),0,dp(4));inspection.addView(art,fill);
        inspection.addView(button("View Card",enlarge),MATCH,dp(48));
        for(PyObject system:host.read("systems",id).asList()){
            String number=system.get("number").toString(),systemName=system.get("name").toString();
            PyObject current=unit.get("remote_weapon_hp").asMap().get(PyObject.fromJava(number));
            LinearLayout row=line(inspection);
            Button view=button(systemName,()->menus.displayCard(system,false));
            view.setContentDescription("Inspect "+systemName+" system card");row.addView(view,weighted(1,dp(48)));
            Button action=button("",()->{
                if(!launchSystems.remove(number))launchSystems.add(number);
                draftChanged();
            });
            row.addView(action,dp(122),dp(48));
            systemReadouts.add(()->{
                boolean inPlay=deployed && current!=null,queued=launchSystems.contains(number);
                action.setText(inPlay?"HP "+current+"/"+system.get("hp"):queued?"Undo launch":editable?"Deploy RWS":"In supply");
                action.setEnabled(editable && !inPlay && (queued || deployed && hp.positive()));
            });
        }
    }
    private void buildState(LinearLayout section){
        int max=card.get("hp").toInt();
        hp=counter(section,"HP","hp","hp",max,Math.min(24,max),ConsoleSkin.TEAM[side]);
        energy=counter(section,"Energy","energy","energy",Integer.MAX_VALUE,10,0xfff1d36a);
        section.addView(caption("Status effects"));
        LinearLayout row=line(section);row.setBaselineAligned(false);
        for(int i=0;i<conditions.length;i++){
            String status=CONDITIONS[i];CheckBox box=new CheckBox(host);conditions[i]=box;
            box.setButtonDrawable((Drawable)null);box.setGravity(Gravity.CENTER);box.setTypeface(ConsoleSkin.font(host));
            box.setText(status);box.setTextSize(13);box.setTextColor(ConsoleSkin.INK);
            Drawable icon=icon(CONDITION_ART[i],32);box.setCompoundDrawables(null,icon,null,null);
            box.setBackground(ConsoleSkin.plate(host,ConsoleSkin.WELL,ConsoleSkin.WELL,ConsoleSkin.EDGE));
            box.setIncludeFontPadding(false);box.setCompoundDrawablePadding(dp(2));
            box.setPadding(dp(4),dp(6),dp(4),dp(6));box.setMinHeight(dp(61));
            box.setChecked(unit.get("statuses").asList().contains(PyObject.fromJava(status)));
            icon.setAlpha(box.isChecked()?255:68);box.setEnabled(editable);
            box.setOnCheckedChangeListener((v,on)->{icon.setAlpha(on?255:68);box.setEnabled(editable && (deployed || on));v.invalidate();draftChanged();});
            row.addView(box,weighted(1,WRAP));
        }
        reserve=button("Return to Reserve",()->deployment(false));
        if(editable)section.addView(reserve);
    }
    private void deployment(boolean next){
        deployed=next;if(!next)launchSystems.clear();
        for(CheckBox box:conditions) box.setEnabled(editable && (deployed || box.isChecked()));
        deploy.setText(deployed?"Deployed":editable?"Deploy":"Reserve");
        ConsoleSkin.primary(deploy);deploy.setEnabled(editable && !deployed);reserve.setEnabled(editable && deployed);draftChanged();
    }
    static Drawable upgradeIcon(TabletActivity host,String name){
        // Give both compound drawables and ImageButtons exactly the same artwork bounds.
        int size=host.dp(34);
        android.graphics.drawable.LayerDrawable token=new android.graphics.drawable.LayerDrawable(
                new Drawable[]{ConsoleSkin.art(host,"unit-tokens/"+name+".png")});
        token.setLayerSize(0,size,size);token.setLayerGravity(0,Gravity.CENTER);
        token.setBounds(0,0,size,size);
        return token;
    }
    private Drawable icon(String name,int size){
        Drawable d=ConsoleSkin.art(host,"unit-tokens/"+name+".png");d.setBounds(0,0,dp(size),dp(size));return d;
    }
    private BayCounter counter(LinearLayout parent,String label,String asset,String key,int max,int pips,int color){
        BayCounter c=new BayCounter(host,label,asset,unit.get(key).toInt(),max,pips,color,editable,this::draftChanged);
        parent.addView(c);return c;
    }
    private void buildUpgrades(LinearLayout section){
        section.addView(caption("Shields"));LinearLayout row=line(section);
        List<PyObject> slots=unit.get("shields").asList();
        for(int i=0;i<shield.length;i++){
            final int slot=i;
            shield[i]=java.util.Arrays.asList(SHIELDS).indexOf(slots.get(i).toString());
            Button b=ConsoleSkin.button(host);b.setTextSize(12);b.setPadding(dp(2),dp(4),dp(2),0);b.setEnabled(editable);
            Runnable paint=()->{
                int state=shield[slot];Drawable d=upgradeIcon(host,"shields-upgrade");
                if(state==0)d.setAlpha(65);
                else if(state==2)d.setColorFilter(new android.graphics.ColorMatrixColorFilter(new float[]{
                        .40f,.38f,.12f,0,26, .18f,.25f,.07f,0,12, .14f,.20f,.06f,0,12, 0,0,0,1,0}));
                b.setCompoundDrawables(null,d,null,null);b.setText((slot+1)+" "+SHIELD_LABELS[state]);
                b.setContentDescription("Shield "+(slot+1)+" "+SHIELD_LABELS[state]);
            };
            paintShields[i]=paint;
            paint.run();b.setOnClickListener(v->{shield[slot]=(shield[slot]+1)%3;paint.run();draftChanged();});
            row.addView(b,weighted(1,dp(UPGRADE_TILE_HEIGHT_DP)));
        }
        List<PyObject> extra=unit.get("extra_shields").asList();
        if(extra.get(0).toInt()+extra.get(1).toInt()>0){
            keepOld=new CheckBox(host);keepOld.setText("Keep older Shields (+"+extra.get(0)+" active, +"+extra.get(1)+" inactive)");
            keepOld.setChecked(true);keepOld.setEnabled(editable);section.addView(keepOld);
            keepOld.setOnCheckedChangeListener((v,on)->draftChanged());
        }
        LinearLayout counters=new LinearLayout(host);counters.setGravity(Gravity.CENTER_VERTICAL);
        section.addView(counters,new LinearLayout.LayoutParams(MATCH,WRAP,1));
        LinearLayout left=column(),right=column();counters.addView(left,weighted(1,WRAP));counters.addView(right,weighted(1,WRAP));
        strength=counter(left,"Strength","strength-upgrade","strength",Integer.MAX_VALUE,0,0);
        speed=counter(right,"Speed","speed-upgrade","speed",Integer.MAX_VALUE,0,0);
    }
    private JSONObject fields(boolean validate){
        try{
            JSONArray statuses=new JSONArray(),tokens=new JSONArray(),timeline=new JSONArray();
            for(int i=0;i<conditions.length;i++)if(conditions[i].isChecked())statuses.put(CONDITIONS[i]);
            for(int i:shield)tokens.put(SHIELDS[i]);for(int n:schedule.values())timeline.put(n);
            JSONObject upgrades=new JSONObject().put("strength",validate?strength.value():strength.raw()).put("speed",validate?speed.value():speed.raw());
            return new JSONObject().put("hp",validate?hp.value():hp.raw()).put("energy",validate?energy.value():energy.raw())
                    .put("upgrades",upgrades).put("deployed",deployed).put("statuses",statuses).put("shield_slots",tokens)
                    .put("launch_systems",new JSONArray(launchSystems)).put("keep_extra_shields",keepOld==null||keepOld.isChecked()).put("timeline",timeline).put("note",note.getText().toString());
        }catch(JSONException e){throw new IllegalStateException(e);}
    }
    android.os.Bundle draft(){
        android.os.Bundle state=new android.os.Bundle();
        state.putString("fields",snapshot());state.putInt("scroll",scroll.getScrollY());return state;
    }
    void restore(android.os.Bundle state){
        if(state==null)return;
        try{
            JSONObject data=new JSONObject(state.getString("fields"));
            hp.restore(data.getString("hp"));energy.restore(data.getString("energy"));
            JSONObject up=data.getJSONObject("upgrades");strength.restore(up.getString("strength"));speed.restore(up.getString("speed"));
            deployment(data.getBoolean("deployed"));
            JSONArray active=data.getJSONArray("statuses"),tokens=data.getJSONArray("shield_slots");
            for(int i=0;i<conditions.length;i++){
                boolean on=false;for(int n=0;n<active.length();n++)on|=CONDITIONS[i].equals(active.getString(n));
                conditions[i].setChecked(on);
            }
            for(int i=0;i<shield.length;i++){
                shield[i]=java.util.Arrays.asList(SHIELDS).indexOf(tokens.getString(i));paintShields[i].run();
            }
            if(keepOld!=null)keepOld.setChecked(data.getBoolean("keep_extra_shields"));
            JSONArray systems=data.getJSONArray("launch_systems");
            for(int i=0;i<systems.length();i++)launchSystems.add(systems.getString(i));
            JSONArray to=data.getJSONArray("timeline");schedule.restore(to.getInt(0),to.getInt(1),to.getInt(2));
            note.setText(data.getString("note"));draftChanged();
            scroll.post(()->scroll.scrollTo(0,state.getInt("scroll")));
        }catch(JSONException e){throw new IllegalStateException(e);}
    }
    @Override public void show(){super.show();TabletDisplay.apply(host,getWindow());}
    private String snapshot(){return fields(false).toString();}
    private void draftChanged(){
        if(original==null)return;
        for(Runnable paint:systemReadouts)paint.run();
        boolean dirty=!original.equals(snapshot());notice.setTextColor(dirty?ConsoleSkin.AMBER:ConsoleSkin.INK);
        notice.setText(!editable?"Match complete · Read-only":dirty?"Unsaved unit changes":"Unit state loaded");
    }
    private void save(){
        if(!editable)return;
        try{
            if(!host.save("service",id,fields(true).toString()))return;
            dismiss();if(deployed && !wasDeployed)host.deploymentEffect();
        }catch(IllegalArgumentException e){notice.setTextColor(ConsoleSkin.AMBER);notice.setText(e.getMessage());}
    }
    private void leave(){
        if(!editable || original.equals(snapshot())){dismiss();return;}
        ConsoleSkin.dialog(host).setTitle("Unsaved unit changes").setMessage("Save this unit before leaving Service Bay?")
                .setPositiveButton("Save unit",(d,w)->save()).setNegativeButton("Discard",(d,w)->dismiss())
                .setNeutralButton("Keep editing",null).show();
    }
    @Override public void onBackPressed(){leave();}
}
