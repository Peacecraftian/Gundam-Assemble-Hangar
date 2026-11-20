package app.hangar.prototype;

import android.app.AlertDialog;
import android.app.Dialog;
import android.graphics.BitmapFactory;
import android.view.Gravity;
import android.widget.*;
import com.chaquo.python.PyObject;
import java.io.IOException;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.List;
import org.json.JSONArray;

final class ConsoleMenus {
    private final TabletActivity host;
    ConsoleMenus(TabletActivity host) { this.host = host; }
    private int integer(PyObject o, String key) { return o.get(key).toInt(); }
    private AlertDialog.Builder dialog(String title) { return ConsoleSkin.dialog(host).setTitle(title); }
    private int phase() { return integer(host.match(),"phase"); }
    private int phases() { return integer(host.match(),"phases"); }

    void score(int side, boolean goal) {
        ConsoleForm form = new ConsoleForm(host);
        Spinner player = form.choices("Scoring player",new String[]{host.playerName(0),host.playerName(1)},side);
        EditText phase = form.number("Scoring Phase",phase(),1,phases());
        int min = Integer.MIN_VALUE;
        EditText points = form.number("Victory Points",1,min,Integer.MAX_VALUE);
        EditText note = form.text(goal ? "Note (optional)" : "Reason","");
        form.show(goal ? "Scenario Goal" : "Adjust VP","Record points",() -> {
            int vp = form.value(points,min,Integer.MAX_VALUE);
            String reason = note.getText().toString().trim();
            if (vp == 0 || (!goal && reason.isEmpty())) throw new IllegalArgumentException("Enter a nonzero score and a reason.");
            if (goal) reason = reason.isEmpty() ? "Scenario goal" : "Scenario goal · " + reason;
            int owner = player.getSelectedItemPosition();
            boolean saved = host.save("score",owner,form.value(phase,1,phases()),vp,reason);
            if (goal && saved && vp>0) host.goalEffect(owner,vp);
            return saved;
        });
    }

    void history() {
        List<PyObject> scores = host.match().get("scores").asList();
        String[] lines = new String[scores.size()];
        for (int i = 0; i < scores.size(); i++) {
            PyObject s = scores.get(scores.size()-1-i);
            int points = integer(s,"points");
            lines[i] = host.playerName(integer(s,"player")) + "   " + (points > 0 ? "+" : "") + points
                    + " VP   ·   Phase " + s.get("phase") + "\n" + s.get("reason");
        }
        AlertDialog.Builder d = dialog("VP History");
        if (lines.length == 0) d.setMessage("No points recorded yet.");
        else d.setItems(lines,null);
        d.setPositiveButton("Close",null).show();
    }

    void matchMenu() {
        if (!host.active()) {
            dialog("Completed match").setItems(new String[]{"VP History",TabletDisplay.label(host)},(d,i)->{
                if (i==0) history(); else TabletDisplay.toggle(host);
            }).setNegativeButton("Close",null).show();
            return;
        }
        String[] choices = {"Previous round","Next round","Jump to Phase and round","VP History",TabletDisplay.label(host)};
        dialog("Match controls").setItems(choices,(d,i) -> {
            if (i < 2) {
                PyObject next = host.match().callAttr("adjacent_cursor",i == 0 ? -1 : 1);
                if (next != null) host.save("cursor",next.asList().get(0).toInt(),next.asList().get(1).toInt());
                else Toast.makeText(host,i == 0 ? "First round of the match" : "Final round of the match",Toast.LENGTH_SHORT).show();
            } else if (i == 2) clock();
            else if (i == 3) history();
            else TabletDisplay.toggle(host);
        }).setNegativeButton("Close",null).show();
    }

    void step(int direction) {
        PyObject next=host.match().callAttr("adjacent_cursor",direction);
        if(next!=null) host.save("cursor",next.asList().get(0).toInt(),next.asList().get(1).toInt());
    }

    void otherPhases() {
        ArrayList<PyObject> other=new ArrayList<>();
        for(PyObject u:host.match().get("units").asList()) if(integer(u,"phase")!=phase()) other.add(u);
        other.sort(java.util.Comparator.<PyObject>comparingInt(u->integer(u,"phase")).thenComparingInt(u->integer(u,"round"))
                .thenComparingInt(u->integer(u,"player")).thenComparingInt(u->integer(u,"stack")));
        String[] labels=new String[other.size()];
        for(int i=0;i<labels.length;i++) {
            PyObject u=other.get(i);
            labels[i]="Phase "+u.get("phase")+" · Round "+u.get("round")+" · "+host.playerName(integer(u,"player"))+" · "+u.get("label");
        }
        dialog("Other phases").setItems(labels,(d,i)->host.inspectUnit(integer(other.get(i),"id"))).setNegativeButton("Close",null).show();
    }

    private void clock() {
        ConsoleForm form = new ConsoleForm(host);
        EditText phase = form.number("Phase",phase(),1,phases());
        EditText round = form.number("Round",integer(host.match(),"round"),1,10);
        form.show("Jump to Phase and round","Jump",() -> host.save("cursor",form.value(phase,1,phases()),form.value(round,1,10)));
    }

    void finish() {
        int a = host.match().callAttr("total",0).toInt(), b = host.match().callAttr("total",1).toInt();
        String title = host.playerName(0) + "  " + a + "   ·   " + host.playerName(1) + "  " + b;
        AlertDialog.Builder d = dialog(title).setNegativeButton("Cancel",null);
        if (a == b) {
            d.setMessage("Tied game. Which player acted last?")
                    .setNeutralButton(host.playerName(0),(dlg,w) -> host.save("finish",0))
                    .setPositiveButton(host.playerName(1),(dlg,w) -> host.save("finish",1));
        } else {
            d.setMessage("Finish the match with " + host.playerName(a > b ? 0 : 1) + " as the winner?")
                    .setPositiveButton("Finish match",(dlg,w) -> host.save("finish",-1));
        }
        d.show();
    }

    private ServiceBay bay;
    void service(){openService(null);}
    void openService(android.os.Bundle draft){
        bay=new ServiceBay(host,this);bay.setOnDismissListener(d->bay=null);bay.show();bay.restore(draft);
    }
    android.os.Bundle bayDraft(){return bay!=null && bay.isShowing()?bay.draft():null;}
    void closeService(){if(bay!=null)bay.dismiss();}

    void schedule() {
        PyObject u=host.unit();
        int id=host.selectedId();
        ConsoleForm f=new ConsoleForm(host);
        TokenSchedule schedule=new TokenSchedule(f,u);
        f.show("Schedule " + u.get("label"),"Move token",() -> {
            int[] to=schedule.values();return host.save("schedule",id,to[0],to[1],to[2]);
        });
    }

    String remoteLabel() {
        return host.unit().get("remote_weapon_hp").asMap().isEmpty() ? "Deploy RWS" : "Manage RWS";
    }
    void remoteShortcut() {
        List<PyObject> systems=host.read("systems",host.selectedId()).asList();
        if (systems.size()==1 && host.unit().get("remote_weapon_hp").asMap().isEmpty()) {
            host.save("deploy_system",host.selectedId(),systems.get(0).get("number").toString());
        } else systems();
    }
    void systems() {
        List<PyObject> all=host.read("systems",host.selectedId()).asList();
        if (all.size()==1) { system(all.get(0)); return; }
        String[] names=new String[all.size()];
        for (int i=0;i<names.length;i++) names[i]=all.get(i).get("name").toString();
        dialog("Remote Weapon Systems").setItems(names,(d,i) -> system(all.get(i))).show();
    }

    private void system(PyObject w) {
        int id=host.selectedId();
        String number=w.get("number").toString();
        PyObject hp=host.unit().get("remote_weapon_hp").asMap().get(PyObject.fromJava(number));
        ArrayList<String> actions=new ArrayList<>();
        actions.add("View system card");
        if (hp==null) actions.add("Deploy RWS");
        else {
            actions.add("Decrease system HP");
            if (hp.toInt()<integer(w,"hp")) actions.add("Restore system HP");
        }
        dialog(w.get("name") + (hp==null ? " · In supply" : " · HP " + hp + "/" + w.get("hp")))
                .setItems(actions.toArray(new String[0]),(d,i) -> {
                    if (i==0) displayCard(w,false);
                    else if (hp==null) host.save("deploy_system",id,number);
                    else if (i==1 && hp.toInt()==1) {
                        dialog("Defeat " + w.get("name") + "?").setMessage("Award " + w.get("vp") + " VP to the opposing player and return the system to supply.")
                                .setNegativeButton("Cancel",null).setPositiveButton("Defeat system",(dlg,k) -> host.save("system_hp",id,number,-1)).show();
                    } else host.save("system_hp",id,number,i==1 ? -1 : 1);
                }).setNegativeButton("Close",null).show();
    }

    void defeatWithSystems(int id) {
        PyObject u=host.read("unit",id);
        List<PyObject> systems=host.read("systems",id).asList();
        ArrayList<String> names=new ArrayList<>(), numbers=new ArrayList<>();
        for (PyObject w:systems) {
            String number=w.get("number").toString();
            if (!u.get("remote_weapon_hp").asMap().containsKey(PyObject.fromJava(number))) continue;
            names.add(w.get("name") + " · " + w.get("vp") + " VP");
            numbers.add(number);
        }
        boolean[] checked=new boolean[names.size()];
        dialog("Which systems were also defeated?").setMultiChoiceItems(names.toArray(new String[0]),checked,(d,i,on) -> checked[i]=on)
                .setNegativeButton("Cancel",null).setPositiveButton("Record defeat",(d,k) -> {
                    JSONArray casualties=new JSONArray();
                    for (int i=0;i<checked.length;i++) if (checked[i]) casualties.put(numbers.get(i));
                    if (host.save("unit_defeat",id,casualties.toString())) host.unitDefeated(id);
                }).show();
    }

    void cardTouches(WeaponCardView art,Runnable fallback,Runnable close){
        art.setOnClickListener(v->fallback.run());
        android.view.GestureDetector detector=new android.view.GestureDetector(host,
                new android.view.GestureDetector.SimpleOnGestureListener(){
            private int touchedUnit,downWeapon;
            @Override public boolean onDown(android.view.MotionEvent e){
                touchedUnit=host.selectedId();
                downWeapon=art.weaponAt(e.getX(),e.getY());
                art.pressWeapon(downWeapon);
                return true;
            }
            @Override public boolean onScroll(android.view.MotionEvent first,android.view.MotionEvent now,float dx,float dy){
                art.pressWeapon(-1);return true;
            }
            @Override public boolean onDoubleTap(android.view.MotionEvent e){
                art.pressWeapon(-1);
                if(close!=null)close.run();else fallback.run();
                return true;
            }
            @Override public boolean onSingleTapConfirmed(android.view.MotionEvent e){
                if(touchedUnit!=host.selectedId())return true;
                if(host.active() && host.unit().get("deployed").toBoolean()){
                    float x=e.getX(),y=e.getY();
                    int index=art.weaponAt(x,y);
                    if(index>=0 && index==downWeapon){
                        art.performHapticFeedback(android.view.HapticFeedbackConstants.VIRTUAL_KEY);
                        if(close!=null)close.run();
                        host.beginAttack(index);return true;
                    }
                    for(PyObject w:host.read("systems",touchedUnit).asList())if(art.hits(w.get("icon_bounds"),x,y)){
                        if(close!=null)close.run();
                        system(w);return true;
                    }
                }
                if(close==null)art.performClick();
                return true;
            }
        });
        art.setOnTouchListener((v,e)->{
            int action=e.getActionMasked();
            if(action==android.view.MotionEvent.ACTION_UP || action==android.view.MotionEvent.ACTION_CANCEL)art.pressWeapon(-1);
            return detector.onTouchEvent(e);
        });
    }

    void fullCard() { displayCard(host.unit().get("card"),true); }

    void displayCard(PyObject card, boolean unitCard) {
        displayCard(card, unitCard, card.get("image").toString());
    }

    void displayCard(PyObject card, boolean unitCard, String imagePath) {
        Dialog d=new Dialog(host,android.R.style.Theme_Material_NoActionBar_Fullscreen);
        LinearLayout page=new LinearLayout(host);
        page.setFitsSystemWindows(true);
        page.setOrientation(LinearLayout.VERTICAL);
        ConsoleSkin.background(page);
        LinearLayout header=new LinearLayout(host);
        header.setGravity(Gravity.CENTER_VERTICAL);
        page.addView(header);
        TextView title=new TextView(host);
        title.setText(unitCard ? host.unit().get("label").toString() : card.get("name").toString());
        title.setTextSize(20);
        header.addView(title,new LinearLayout.LayoutParams(0,-2,1));
        title.setTypeface(ConsoleSkin.font(host));title.setPadding(host.dp(12),0,0,0);
        LinearLayout footer=new LinearLayout(host);footer.setGravity(Gravity.RIGHT|Gravity.CENTER_VERTICAL);
        ConsoleSkin.panel(footer,ConsoleSkin.PANEL);
        if(unitCard && !host.read("systems",host.selectedId()).asList().isEmpty()){
            PyObject w=host.read("systems",host.selectedId()).asList().get(0);
            TextView supply=ConsoleSkin.title(host,w.get("name")+" · "+(host.unit().get("remote_weapon_hp").asMap().isEmpty()?"In supply":"Deployed"),14);
            footer.addView(supply,new LinearLayout.LayoutParams(0,-1,1));
            if(host.active() && host.unit().get("deployed").toBoolean()){
                Button rws=ConsoleSkin.button(host);ConsoleSkin.primary(rws);
                rws.setText(remoteLabel());rws.setOnClickListener(v->{d.dismiss();remoteShortcut();});
                footer.addView(rws,host.dp(122),host.dp(48));
            }
        }
        if(unitCard && host.active() && host.unit().get("deployed").toBoolean()){
            Button attack=ConsoleSkin.button(host);attack.setText("Attack");
            attack.setOnClickListener(v->{d.dismiss();host.beginAttack(0);});footer.addView(attack,host.dp(122),host.dp(48));
        }
        Button close=ConsoleSkin.button(host);close.setText("Close card");
        close.setOnClickListener(v->d.dismiss());footer.addView(close,host.dp(122),host.dp(48));
        WeaponCardView art=new WeaponCardView(host);
        try (InputStream in=host.getAssets().open(imagePath)) {
            art.setImageBitmap(BitmapFactory.decodeStream(in));
        } catch (IOException ex) {throw new IllegalStateException(ex);}
        art.setContentDescription(card.get("name")+" full card");
        art.setScaleType(ImageView.ScaleType.FIT_CENTER);
        if(unitCard){
            List<PyObject> weapons=host.active() && host.unit().get("deployed").toBoolean()
                    ?host.read("attacks",host.selectedId()).asList():java.util.Collections.emptyList();
            art.setWeapons(weapons);
            if(!weapons.isEmpty()){
                TextView hint=ConsoleSkin.title(host,WeaponCardView.ATTACK_HINT,13);
                hint.setTextColor(ConsoleSkin.AMBER);hint.setPadding(host.dp(8),0,host.dp(12),0);header.addView(hint);
            }
            cardTouches(art,d::dismiss,d::dismiss);
        }
        else art.setOnClickListener(v -> d.dismiss());
        page.addView(art,new LinearLayout.LayoutParams(-1,0,1));
        page.addView(footer);
        d.setContentView(page);
        d.show();
    }
}
