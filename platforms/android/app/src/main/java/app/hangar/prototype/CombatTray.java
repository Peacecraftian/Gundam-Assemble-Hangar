package app.hangar.prototype;

import android.app.Dialog;
import android.view.Gravity;
import android.view.WindowManager;
import android.view.ViewGroup;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceRequest;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.*;
import com.chaquo.python.PyObject;
import java.util.ArrayList;
import java.util.List;
import org.json.JSONException;
import org.json.JSONObject;

final class CombatTray {
    private final TabletActivity host;
    CombatTray(TabletActivity host) { this.host=host; }

    void freeRoll() { open("Dice tray",null,3,0); }

    private static final class Attack {
        final int attacker, target;
        final PyObject weapon;
        final boolean disarmed;
        Attack(int attacker,int target,PyObject weapon,boolean disarmed) {
            this.attacker=attacker; this.target=target; this.weapon=weapon; this.disarmed=disarmed;
        }
    }

    void attack(int index) {
        String pending=host.read("pending").toString();
        if (!pending.isEmpty()) { resume(pending); return; }
        int attacker=host.selectedId();
        List<PyObject> weapons=host.read("attacks",attacker).asList();
        List<PyObject> foes=new ArrayList<>();
        for (PyObject u:host.match().get("units").asList())
            if (u.get("player").toInt()!=host.owner() && u.get("deployed").toBoolean()) foes.add(u);
        if (!host.unit().get("deployed").toBoolean() || weapons.isEmpty()) {
            Toast.makeText(host,"Deploy an attacker first.",Toast.LENGTH_LONG).show();
            return;
        }
        String[] names=new String[weapons.size()];
        for (int i=0;i<weapons.size();i++) {
            PyObject w=weapons.get(i);
            names[i]=w.get("name")+" · TL "+w.get("timeline")+" · Range "+w.get("range")+" · STR "+w.get("strength");
        }
        ConsoleForm f=new ConsoleForm(host);
        Spinner weapon=f.choices("Weapon",names,index);
        f.label("Enemy target");
        RadioGroup targets=new RadioGroup(host);f.body.addView(targets);
        int side=1-host.owner();
        for(int i=0;i<foes.size();i++){
            PyObject unit=foes.get(i);
            RadioButton candidate=new RadioButton(host);
            candidate.setId(android.view.View.generateViewId());candidate.setTag(i);
            candidate.setTypeface(ConsoleSkin.font(host));candidate.setText(host.playerName(side)+" · "+unit.get("label"));
            candidate.setTextColor(ConsoleSkin.TEAM[side]);candidate.setMinHeight(host.dp(54));
            android.graphics.drawable.Drawable portrait=ConsoleSkin.art(host,"portraits/"+unit.get("card").get("number")+".webp");
            portrait.setBounds(0,0,host.dp(48),host.dp(36));candidate.setCompoundDrawables(portrait,null,null,null);
            candidate.setCompoundDrawablePadding(host.dp(8));
            targets.addView(candidate);if(i==0)targets.check(candidate.getId());
        }
        RadioButton garrison=new RadioButton(host);
        garrison.setId(android.view.View.generateViewId());garrison.setTag(foes.size());
        garrison.setText("Enemy Garrison · 1 HP · 2 VP");garrison.setTextColor(ConsoleSkin.TEAM[side]);
        garrison.setMinHeight(host.dp(54));targets.addView(garrison);
        if(foes.isEmpty()) targets.check(garrison.getId());
        int strength=host.unit().get("strength").toInt();
        EditText upgrades=f.number("Strength upgrades",strength,0,Integer.MAX_VALUE);
        EditText modifier=f.number("Other strength modifier",0,-60,60);
        EditText accuracy=f.number("Accuracy modifier",0,-99,99);
        f.label("Declaring pays the weapon TL now. Undo takes back the whole attack.");
        f.show("Weapon attack","Declare & roll",() -> {
            PyObject w=weapons.get(weapon.getSelectedItemPosition());
            int row=(Integer)targets.findViewById(targets.getCheckedRadioButtonId()).getTag();
            int target=row==foes.size()?0:foes.get(row).get("id").toInt();
            long count=(long)w.get("strength").toInt()+f.value(upgrades,0,Integer.MAX_VALUE)+f.value(modifier,-60,60);
            if (count<0 || count>60) throw new IllegalArgumentException("Choose modifiers that give 0–60 dice.");
            if (!host.save("declare",attacker,target,w.get("name").toString(),(int)count,f.value(accuracy,-99,99))) return false;
            resume(host.read("pending").toString());
            return true;
        });
    }

    private void resume(String saved) {
        try {
            JSONObject p=new JSONObject(saved);
            int id=p.getInt("attacker"), target=p.getInt("target");
            PyObject weapon=host.read("weapon",id,p.getString("weapon"));
            Attack a=new Attack(id,target,weapon,p.getBoolean("disarmed"));
            String label=target==0?"Enemy Garrison":host.read("unit",target).get("label").toString();
            open(weapon.get("name")+" → "+label,a,p.getInt("count"),p.getInt("accuracy"));
        } catch(JSONException e) { throw new IllegalStateException("Invalid saved attack",e); }
    }

    private void open(String title, Attack attack, int count, int accuracy) {
        WebView tray=new WebView(host);
        tray.setBackgroundColor(ConsoleSkin.WELL);
        tray.getSettings().setJavaScriptEnabled(true);
        tray.getSettings().setBlockNetworkLoads(true);
        tray.getSettings().setAllowContentAccess(false);
        tray.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request) { return true; }
        });
        Dialog dialog=new Dialog(host,android.R.style.Theme_Material_NoActionBar);
        LinearLayout page=new LinearLayout(host);
        page.setOrientation(LinearLayout.VERTICAL);page.setFitsSystemWindows(true);
        page.setFocusableInTouchMode(true);ConsoleSkin.background(page);
        LinearLayout header=new LinearLayout(host);header.setGravity(Gravity.CENTER_VERTICAL);
        ConsoleSkin.panel(header,ConsoleSkin.PANEL);page.addView(header,-1,host.dp(52));
        TextView label=ConsoleSkin.title(host,title,20);
        label.setGravity(Gravity.START|Gravity.CENTER_VERTICAL);label.setPadding(host.dp(14),0,host.dp(8),0);
        header.addView(label,new LinearLayout.LayoutParams(0,-1,1));
        Button close=ConsoleSkin.button(host);close.setText("Close");close.setOnClickListener(v->dialog.dismiss());
        header.addView(close,host.dp(96),host.dp(48));
        Button resolve=ConsoleSkin.button(host);
        if(attack!=null){
            resolve.setText("Resolve damage");ConsoleSkin.primary(resolve);header.addView(resolve,host.dp(144),host.dp(48));
        }
        page.addView(tray,new LinearLayout.LayoutParams(-1,0,1));
        dialog.setContentView(page);
        dialog.getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE|WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_HIDDEN);
        if (attack!=null) {
            tray.addJavascriptInterface(new Object() {
                @JavascriptInterface public void settled(String values,int accuracy,boolean mandatory) {
                    host.runOnUiThread(() -> {
                        if (!dialog.isShowing()) return;
                        if (host.save("settle_roll",values,accuracy,mandatory)) tray.evaluateJavascript("rollSaved("+mandatory+")",null);
                        else dialog.dismiss();
                    });
                }
            },"RollHost");
        }
        dialog.setOnDismissListener(d -> {
            tray.removeJavascriptInterface("RollHost");
            if (tray.getParent()!=null) ((ViewGroup)tray.getParent()).removeView(tray);
            tray.destroy();
        });
        dialog.show();
        TabletDisplay.apply(host,dialog.getWindow());
        if (attack!=null) resolve.setOnClickListener(v ->
                tray.evaluateJavascript("snapshot()",json -> {
                    if (!dialog.isShowing()) return;
                    if (json==null || json.equals("null")) {
                        Toast.makeText(host,"Finish the roll and resolve any pending Disarm first.",Toast.LENGTH_LONG).show();
                        return;
                    }
                    try { damage(attack,new JSONObject(json),dialog); }
                    catch (JSONException e) { Toast.makeText(host,"Unable to read this roll.",Toast.LENGTH_SHORT).show(); }
                }));
        String query=attack==null ? "" : "?attack=1&count="+count+"&accuracy="+accuracy+"&saved="+android.net.Uri.encode(host.read("pending").toString());
        tray.loadUrl("file:///android_asset/dice.html"+query);
    }

    private void damage(Attack a,JSONObject roll,Dialog tray) throws JSONException {
        String values=roll.getJSONArray("values").toString();
        int accuracy=roll.getInt("accuracy");
        ConsoleForm f=new ConsoleForm(host);
        PyObject target=a.target==0?null:host.read("unit",a.target);
        String name=a.weapon.get("name").toString();
        int bonus=host.read("roll_bonus",a.attacker,name,values).toInt();
        int hits=host.read("attack_hits",values,accuracy,host.read("unit",a.attacker).get("card").get("number").toString()).toInt();
        f.label(a.weapon.get("name")+" · TL paid "+a.weapon.get("timeline")+" · "+hits+" hits on "+(target==null?"Enemy Garrison":target.get("label"))+(bonus>0?" · Rifle damage +"+bonus:""));
        EditText modifier=f.number("Damage modifier",0,-99,99);
        TextView preview=f.label("");
        Runnable update=()-> {
            try {
                int delta=Integer.parseInt(modifier.getText().toString());
                if (delta < -99 || delta > 99) {preview.setText("Enter a modifier from −99 to +99."); return;}
                JSONObject p=new JSONObject(host.read("damage_preview",a.target,hits,delta,bonus).toString());
                preview.setText("Fracture +"+p.getInt("fracture")+"  ·  Shields block "+p.getInt("shields")
                        +"  ·  "+p.getInt("hp_loss")+" damage\n"+(p.getBoolean("defeat")?(target==null?"Remove Garrison · +2 VP":"Unit will be defeated"):p.getInt("remaining")+" HP remaining"));
            } catch (NumberFormatException|JSONException e) {preview.setText("Enter a whole damage modifier.");}
        };
        modifier.addTextChangedListener(new android.text.TextWatcher() {
            public void beforeTextChanged(CharSequence s,int st,int c,int a){}
            public void onTextChanged(CharSequence s,int st,int before,int count){update.run();}
            public void afterTextChanged(android.text.Editable s){}
        });
        update.run();
        f.show("Apply combat damage","Apply damage",() -> {
            if (!tray.isShowing()) return true;
            boolean defeated=a.target==0 && hits+bonus+f.value(modifier,-99,99)>0;
            if (!host.save("finish_attack",a.attacker,a.target,values,accuracy,f.value(modifier,-99,99),a.weapon.get("name").toString())) return false;
            tray.dismiss();
            if (a.target==0) { if(defeated) host.garrisonDefeated(a.attacker); }
            else if (!host.read("unit",a.target).get("deployed").toBoolean()) host.unitDefeated(a.target);
            return true;
        });
    }
}
