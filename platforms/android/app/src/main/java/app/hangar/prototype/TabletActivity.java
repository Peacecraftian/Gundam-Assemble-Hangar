package app.hangar.prototype;

import android.app.Activity;
import android.app.AlertDialog;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.view.View;
import java.util.ArrayList;
import android.os.Bundle;
import android.graphics.BitmapFactory;
import android.graphics.Typeface;
import android.view.Gravity;
import android.widget.*;
import com.chaquo.python.PyObject;
import com.chaquo.python.Python;
import java.io.*;

public final class TabletActivity extends Activity {
    private PyObject session;
    private int selected = 1;
    private WeaponCardView card;
    private TextView weaponHint;
    private TextView title;
    private final Button[] vitalSteps=new Button[4];
    private TextView phaseLights;
    private Typeface displayFont;
    private Timeline timeline;
    private FrameLayout screen;
    private WebView actionEffect;
    private FrameLayout cardStage;
    private ScrollView consoleViewport;
    private enum EffectPlacement { CARD, FOOTER, SCREEN }
    private ScenarioDesk battlefield;
    private Sortie sortie;
    private final TextView[] totals = new TextView[2];
    private final Button[] goals = new Button[2];
    private Button deploy, matchMenu, service, undo, finishMatch, attack, remote, previous, next;
    private CombatTray combat;
    private HangarReadouts hangars;
    private boolean squadHasRemoteSystems;
    private ConsoleMenus menus;
    private final ArrayList<Button> unitActions = new ArrayList<>();

    private enum Command {
        DASH("Dash", "dash", "Vernier Dash", "dash.html"),
        ENERGIZE("Energize", "energize", "Reactor Surge", "surge.html"),
        DEFEAT("Garrison Defeat", "garrison_defeat", "Garrison explosion", "garrison-defeat.html"),
        RESCUE("Garrison Rescue", "garrison_rescue", "Garrison celebration", "garrison-rescue.html"),
        UNIT_DEFEAT("Unit Defeat", "unit_defeat", "Unit defeated", null);

        final String label, method, effectName, page;

        Command(String label, String method, String effectName, String page) {
            this.label = label;
            this.method = method;
            this.effectName = effectName;
            this.page = page;
        }
    }

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        for (String file : new String[]{"catalog.json", "scenarios.json", "attacks.json", "remote_weapons.json"})
        try (InputStream in = getAssets().open(file);
             OutputStream out = openFileOutput(file, MODE_PRIVATE)) {
            byte[] bytes = new byte[8192];
            int count;
            while ((count = in.read(bytes)) != -1) out.write(bytes, 0, count);
        } catch (IOException ex) { throw new IllegalStateException(ex); }
        session = Python.getInstance().getModule("tablet").callAttr("Session", getFilesDir().toString());
        if (saved != null && match()!=null) {
            int previous=saved.getInt("selected",1);
            for(PyObject unit:units())if(unit.get("id").toInt()==previous){selected=previous;break;}
        }
        displayFont = Typeface.createFromAsset(getAssets(), "ChakraPetch-Bold.ttf");
        if (session.get("match") == null) openSortie();
        else if (getPreferences(MODE_PRIVATE).getBoolean("battlefieldOpen", false)) openBattlefield();
        else {
            openConsole();
            if(saved!=null && saved.containsKey("bay") && saved.getLong("bayRevision")==session.get("revision").toLong())
                menus.openService(saved.getBundle("bay"));
        }
    }

    View header(int tab) {
        return ConsoleSkin.header(this,tab,match()!=null,this::navigate);
    }
    private static final int TACTICS_REQUEST=6903;
    void navigate(int tab) {
        if (tab==3) {
            android.content.Intent i=new android.content.Intent(this,TacticsActivity.class);
            i.putExtra("match",match()!=null);
            startActivityForResult(i,TACTICS_REQUEST);
            return;
        }
        if (tab==1 && battlefield!=null || tab==0 && battlefield==null && sortie!=null ||
                tab==2 && battlefield==null && sortie==null) return;
        Runnable switchPage=()->{
            if (tab==0 && sortie!=null && battlefield!=null) leaveBattlefield();
            else if(tab==0) openSortie();
            else if(tab==1) openBattlefield();
            else if(tab==2 && match()!=null) openConsole();
        };
        if(battlefield!=null) battlefield.discardThen(switchPage); else switchPage.run();
    }

    void openBattlefield() {
        dismissEffect();
        LinearLayout page = pageWithInsets();
        page.addView(header(1));
        battlefield = new ScenarioDesk(this, () -> leaveBattlefield());
        page.addView(battlefield,new LinearLayout.LayoutParams(-1,-1));
        setContentView(page);
        getPreferences(MODE_PRIVATE).edit().putBoolean("battlefieldOpen",sortie==null).apply();
    }

    private void leaveBattlefield() {
        if (sortie == null) { openConsole(); return; }
        closeBattlefield();
        sortie.refreshScenarios();
        setContentView(sortie);
    }

    private void closeBattlefield() {
        if (battlefield == null) return;
        battlefield.close();
        battlefield = null;
    }

    @Override protected void onActivityResult(int request, int result, android.content.Intent data) {
        super.onActivityResult(request,result,data);
        if (request==TACTICS_REQUEST) {
            if(result==RESULT_OK && data!=null) navigate(data.getIntExtra("tab",3));
            return;
        }
        if (battlefield!=null && result==RESULT_OK && data!=null && data.getData()!=null)
            battlefield.fileResult(request,data.getData());
    }
    @Override public void onBackPressed() {
        if (battlefield!=null) battlefield.requestExit();
        else if (sortie!=null && match()!=null) openConsole();
        else super.onBackPressed();
    }

    private void openSortie() {
        dismissEffect();
        closeBattlefield();
        sortie = new Sortie(this, session, displayFont, () -> {
            selected = 1;
            openConsole();
        }, this::openConsole);
        setContentView(sortie);
    }

    private LinearLayout pageWithInsets() {
        LinearLayout page = new LinearLayout(this);
        ConsoleSkin.background(page);
        page.setOnApplyWindowInsetsListener((v, i) -> {
            v.setPadding(dp(16) + i.getSystemWindowInsetLeft(), dp(12) + i.getSystemWindowInsetTop(),
                         dp(16) + i.getSystemWindowInsetRight(), dp(12) + i.getSystemWindowInsetBottom());
            return i;
        });
        page.setOrientation(LinearLayout.VERTICAL);
        return page;
    }

    private void openConsole() {
        closeBattlefield();
        sortie = null;
        getPreferences(MODE_PRIVATE).edit().putBoolean("battlefieldOpen", false).apply();
        LinearLayout page = pageWithInsets();
        screen = new FrameLayout(this);
        // Let a crowded Timeline or a short tablet scroll before consuming the card rails' minimum height.
        ScrollView compact=new ScrollView(this);consoleViewport=compact;compact.setFillViewport(true);
        page.setOnApplyWindowInsetsListener(null);page.setPadding(dp(16),dp(12),dp(16),dp(12));
        compact.setOnApplyWindowInsetsListener((v,i)->{
            v.setPadding(i.getSystemWindowInsetLeft(),i.getSystemWindowInsetTop(),i.getSystemWindowInsetRight(),i.getSystemWindowInsetBottom());
            return i;
        });
        compact.addView(page);screen.setBackgroundColor(ConsoleSkin.WELL);screen.addView(compact);
        setContentView(screen);
        PyObject match = session.get("match");
        page.addView(header(2));
        menus = new ConsoleMenus(this);
        combat = new CombatTray(this);
        unitActions.clear();
        LinearLayout scores = new LinearLayout(this);
        page.addView(scores, spaced(-1,-2));
        playerPanel(scores,0);
        LinearLayout clock = column(scores,.70f,ConsoleSkin.PANEL);
        String mission=match.get("scenario").toString();
        clock.addView(ConsoleSkin.title(this,mission.isEmpty()?"Game Controls":mission,15));
        phaseLights=ConsoleSkin.title(this,"",12);clock.addView(phaseLights);
        LinearLayout stepper=actionRow(clock);
        previous=roundArrow(stepper,"‹","Previous round",0,-1);
        matchMenu=button(stepper,"",menus::matchMenu);
        next=roundArrow(stepper,"›","Next round",2,1);
        playerPanel(scores,1);

        timeline = new Timeline(this, displayFont, match.get("players").asList(), new Timeline.Actions() {
            public void select(int id) { TabletActivity.this.select(id); }
            public void inspect(int id) { select(id); menus.service(); }
            public void schedule() { menus.schedule(); }
            public void otherPhases() { menus.otherPhases(); }
            public void move(int id,int round,int position) {
                if (active()) save("schedule",id,match().get("phase").toInt(),round,position);
            }
        });
        ConsoleSkin.panel(timeline,ConsoleSkin.PANEL);
        page.addView(timeline,spaced(-1,-2));
        LinearLayout detail=new LinearLayout(this);
        boolean wide=getResources().getConfiguration().screenWidthDp>=1120;
        page.addView(detail,new LinearLayout.LayoutParams(-1,dp(wide?280:346),1));
        hangars=new HangarReadouts(this);
        detail.addView(hangars.team(0),new LinearLayout.LayoutParams(0,-1,1));
        LinearLayout display=column(detail,1.65f,ConsoleSkin.PANEL);
        LinearLayout heading=actionRow(display);
        title=ConsoleSkin.title(this,"",15);
        title.setGravity(Gravity.START|Gravity.CENTER_VERTICAL);
        LinearLayout identity=new LinearLayout(this);
        identity.setGravity(Gravity.CENTER_VERTICAL);identity.setOrientation(LinearLayout.VERTICAL);
        identity.addView(title);
        weaponHint=ConsoleSkin.title(this,WeaponCardView.ATTACK_HINT,11);weaponHint.setTextColor(ConsoleSkin.AMBER);
        weaponHint.setGravity(Gravity.START);identity.addView(weaponHint);
        if(wide)heading.addView(identity,dp(122),-1);
        else heading.addView(identity,new LinearLayout.LayoutParams(0,-1,1));
        LinearLayout vitals=new LinearLayout(this);vitals.setGravity(Gravity.CENTER);
        if(wide)heading.addView(vitals,new LinearLayout.LayoutParams(0,dp(48),1));
        service=ConsoleSkin.button(this);service.setText("Service Bay");service.setOnClickListener(v->menus.service());
        ConsoleSkin.primary(service);service.setCompoundDrawables(ConsoleSkin.hazard(this),null,null,null);
        heading.addView(service,dp(116),dp(48));
        if(!wide)display.addView(vitals,-1,dp(48));
        counter(vitals,"HP",0);counter(vitals,"Energy",2);
        card=new WeaponCardView(this); card.setScaleType(ImageView.ScaleType.FIT_CENTER);
        card.setPadding(dp(3),dp(4),dp(3),dp(4));
        menus.cardTouches(card,menus::fullCard,null);
        LinearLayout cardWell=new LinearLayout(this);ConsoleSkin.panel(cardWell,ConsoleSkin.WELL);
        int inset=dp(2);cardWell.setPadding(inset,inset,inset,inset);
        display.addView(cardWell,new LinearLayout.LayoutParams(-1,0,1));
        cardWell.addView(hangars.rail(0),dp(54),-1);
        cardStage=new FrameLayout(this);
        cardStage.addView(card,new FrameLayout.LayoutParams(-1,-1));
        cardWell.addView(cardStage,new LinearLayout.LayoutParams(0,-1,1));
        cardWell.addView(hangars.rail(1),dp(54),-1);
        if(!wide)display.addView(hangars.selectedMeters(),-1,dp(26));
        LinearLayout actions=actionRow(display);actions.setGravity(Gravity.CENTER_VERTICAL);
        if(wide)actions.addView(hangars.selectedMeters(),new LinearLayout.LayoutParams(0,dp(42),1));
        deploy=button(actions,"Deploy",this::deploySelected);
        attack=button(actions,"Attack",()->combat.attack(0));
        squadHasRemoteSystems = false;
        for (PyObject member : units()) {
            if (!read("systems", member.get("id").toInt()).asList().isEmpty()) {
                squadHasRemoteSystems = true;
                break;
            }
        }
        remote=button(actions,"RWS",menus::remoteShortcut);remote.setContentDescription("RWS");
        Button viewCard=button(actions,"View Card",menus::fullCard);
        if(wide){
            for(Button control:new Button[]{deploy,attack,remote,viewCard}){
                control.setTextSize(12);control.setPadding(dp(4),0,dp(4),0);
                int width=control==remote?84:control==viewCard?72:64;
                control.setLayoutParams(new LinearLayout.LayoutParams(dp(width),dp(46)));
            }
        }
        detail.addView(hangars.team(1),new LinearLayout.LayoutParams(0,-1,1));

        LinearLayout footer=new LinearLayout(this);ConsoleSkin.panel(footer,ConsoleSkin.PANEL);
        page.addView(footer,spaced(-1,-2));
        footerButton(footer,"Dice tray",combat::freeRoll);
        footerButton(footer,"VP History",menus::history);
        undo=footerButton(footer,"Undo",()->{ dismissEffect(); session.callAttr("undo"); refreshTimeline(); refresh(false); });
        footerButton(footer,"New Match",this::openSortie);
        finishMatch=footerButton(footer,"Finish Match",menus::finish);
        refreshTimeline();
        refresh(true);
    }

    private java.util.List<PyObject> units() {
        return session.get("match").get("units").asList();
    }
    boolean fromSortie() {return sortie!=null;}
    PyObject scenarioNames() {return session.get("scenarios");}
    int owner() { return unit().get("player").toInt(); }
    int selectedId() { return selected; }
    PyObject unit() { return session.callAttr("unit", selected); }
    PyObject read(String method, Object... args) { return session.callAttr(method,args); }
    void inspectUnit(int id) {select(id);}
    void beginAttack(int index) { combat.attack(index); }
    PyObject match() { return session.get("match"); }
    boolean active() { return match().get("winner") == null; }
    boolean save(String method, Object... args) {
        try {
            session.callAttr(method, args);
        } catch (com.chaquo.python.PyException e) {
            ConsoleSkin.dialog(this).setTitle("Could not save edit")
                    .setMessage(e.getMessage()).setPositiveButton("OK", null).show();
            return false;
        }
        refreshTimeline();
        refresh(false);
        return true;
    }

    String playerName(int side) {
        return session.get("match").get("players").asList().get(side).toString();
    }
    private void chooseRoster(int side) {
        ArrayList<PyObject> roster = new ArrayList<>();
        for (PyObject unit : units()) if (unit.get("player").toInt() == side) roster.add(unit);
        if (roster.size() == 1) { select(roster.get(0).get("id").toInt()); return; }
        String[] labels = new String[roster.size()];
        for (int i = 0; i < labels.length; i++) labels[i] = roster.get(i).get("label").toString();
        ConsoleSkin.dialog(this).setTitle(playerName(side)).setItems(labels,
                (d, i) -> select(roster.get(i).get("id").toInt())).show();
    }

    private Button roundArrow(LinearLayout row,String label,String desc,int index,int direction) {
        Button b=ConsoleSkin.button(this); b.setText(label); b.setTextSize(20); b.setContentDescription(desc);
        b.setOnClickListener(v->menus.step(direction));
        row.addView(b,index,new LinearLayout.LayoutParams(dp(48),dp(48)));
        return b;
    }

    private LinearLayout actionRow(LinearLayout panel) {
        LinearLayout row = new LinearLayout(this);
        panel.addView(row);
        return row;
    }

    private LinearLayout.LayoutParams spaced(int width,int height) {
        LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(width,height);
        p.setMargins(0,dp(4),0,dp(3));return p;
    }
    private LinearLayout column(LinearLayout parent,float weight,int face) {
        LinearLayout v=new LinearLayout(this);v.setOrientation(LinearLayout.VERTICAL);v.setGravity(Gravity.CENTER_VERTICAL);
        ConsoleSkin.panel(v,face);v.setPadding(dp(4),dp(2),dp(4),dp(2));
        LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(0,-1,weight);
        p.setMargins(dp(2),0,dp(2),0);parent.addView(v,p);return v;
    }
    private void playerPanel(LinearLayout parent,int side) {
        LinearLayout box=column(parent,1.35f,ConsoleSkin.HOUSING[side]);
        box.setOrientation(LinearLayout.HORIZONTAL);
        boolean blue=side==0;
        TextView score=ConsoleSkin.title(this,"00",34);
        totals[side]=score; score.setTypeface(ConsoleSkin.digits(this));score.setTextColor(ConsoleSkin.TEAM[side]);
        score.setMinimumWidth(dp(56));score.setMinimumHeight(dp(50));
        score.setBackground(ConsoleSkin.plate(this,ConsoleSkin.WELL,ConsoleSkin.PANEL,ConsoleSkin.TEAM[side]));
        score.setContentDescription("Victory points for "+playerName(side)); score.setFocusable(true);
        score.setOnClickListener(v->{if(active()) menus.score(side,false);else menus.history();});
        LinearLayout identity=new LinearLayout(this);identity.setOrientation(LinearLayout.VERTICAL);
        TextView tag=ConsoleSkin.title(this,"PLAYER "+(side+1),11);tag.setTypeface(Typeface.MONOSPACE);
        TextView name=ConsoleSkin.title(this,playerName(side),18);name.setTextColor(ConsoleSkin.TEAM[side]);
        identity.addView(tag);identity.addView(name);identity.setOnClickListener(v->chooseRoster(side));
        LinearLayout pad=new LinearLayout(this);pad.setOrientation(LinearLayout.VERTICAL);
        Command[][] rows={{Command.DASH,Command.DEFEAT,Command.UNIT_DEFEAT},{Command.ENERGIZE,Command.RESCUE,null}};
        for(Command[] row:rows) {
            LinearLayout line=actionRow(pad);
            // Align button faces even when a label wraps onto a second line.
            line.setBaselineAligned(false);
            for(int index=0;index<row.length;index++){
                Command cmd=row[blue?index:row.length-1-index];
                Button b=button(line,cmd==null?"Scenario Goal":cmd.label,()->{
                    if(cmd==null) menus.score(side,true);else chooseActor(cmd,side);
                });
                b.setTextSize(12);b.setMaxLines(2);
                ConsoleSkin.finish(b,blue?0xff37564f:0xff57413b,ConsoleSkin.HOUSING[side],blue?0xff577c72:0xff846053,ConsoleSkin.INK);
                if(cmd==null) goals[side]=b;else { b.setTag(cmd==Command.UNIT_DEFEAT?1-side:side); unitActions.add(b); }
            }
        }
        LinearLayout.LayoutParams id=new LinearLayout.LayoutParams(0,-2,.65f),keys=new LinearLayout.LayoutParams(0,-2,1.9f);
        if(getResources().getConfiguration().screenWidthDp<1000){
            box.setOrientation(LinearLayout.VERTICAL);LinearLayout top=new LinearLayout(this);top.setGravity(Gravity.CENTER_VERTICAL);
            box.addView(top);if(blue){top.addView(score);top.addView(identity,id);}else{top.addView(identity,id);top.addView(score);}
            box.addView(pad);return;
        }
        if(blue){box.addView(score);box.addView(identity,id);box.addView(pad,keys);}
        else {box.addView(pad,keys);box.addView(identity,id);box.addView(score);}
    }
    void deployUnit(int id){select(id);deploySelected();}
    private void deploySelected(){
        if (!active() || unit().get("deployed").toBoolean()) return;
        final int actor=selected;
        ConsoleSkin.dialog(this).setTitle("Deploy "+unit().get("label"))
                .setMessage("If both deployment and an Advance to a legal hex are blocked, Energize and remain in Reserve.")
                .setNegativeButton("Cancel",null)
                .setNeutralButton("Blocked · Energize",(d,w)->save("blocked_deployment",actor))
                .setPositiveButton("Deploy",(d,w)->{if(save("deploy",actor)) deploymentEffect();}).show();
    }
    void deploymentEffect(){
        final int side=owner();
        marquee("Deployment",side==0?"Deploy_P1.webp":"Deploy_P2.webp",5500);
        hangars.openDoor(side);
    }

    private void chooseActor(Command command,int side) {
        ArrayList<Integer> ids = new ArrayList<>();
        ArrayList<PyObject> choices = new ArrayList<>();
        ArrayList<String> labels = new ArrayList<>(), systems = new ArrayList<>();
        int eligibleSide=command==Command.UNIT_DEFEAT ? 1-side : side;
        for (PyObject unit : units()) {
            int id = unit.get("id").toInt();
            if (unit.get("player").toInt()==eligibleSide && unit.get("deployed").toBoolean()) {
                ids.add(id);
                choices.add(unit);
                String name=playerName(unit.get("player").toInt())+" · "+unit.get("label");
                labels.add(name); systems.add(null);
                if (command==Command.UNIT_DEFEAT) for (PyObject w:read("systems",id).asList()) {
                    String number=w.get("number").toString();
                    if (unit.get("remote_weapon_hp").asMap().containsKey(PyObject.fromJava(number))) {
                        choices.add(unit); ids.add(id); labels.add(name+" · "+w.get("name")); systems.add(number);
                    }
                }
            }
        }
        if (ids.isEmpty()) return;
        int initial = Math.max(0, ids.indexOf(selected));
        ConsoleSkin.dialog(this).setTitle(command.label + " · Select a deployed unit")
                .setSingleChoiceItems(new UnitChoices(this,choices,android.R.layout.simple_list_item_single_choice,labels), initial, null)
                .setNegativeButton("Cancel", null)
                .setPositiveButton(command.label, (dialog, which) -> {
                    int row = ((AlertDialog)dialog).getListView().getCheckedItemPosition();
                    int id = ids.get(row);
                    if (systems.get(row)!=null) {
                        if (save("defeat_system",id,systems.get(row))) unitDefeated(id);
                        return;
                    }
                    if (command == Command.UNIT_DEFEAT && !session.callAttr("unit",id).get("remote_weapon_hp").asMap().isEmpty()) {
                        menus.defeatWithSystems(id);
                        return;
                    }
                    if (command==Command.DEFEAT) {
                        ConsoleForm cost=new ConsoleForm(this);
                        android.widget.EditText tl=cost.number("Unpaid TL (0 if already paid)",0,0,99);
                        cost.show("Tabletop Garrison defeat · +2 VP","Record defeat",()->{
                            if (!save(command.method,id,cost.value(tl,0,99))) return false;
                            garrisonDefeated(id); return true;
                        });
                        return;
                    }
                    if (!save(command.method, id)) return;
                    select(id);
                    if (command == Command.UNIT_DEFEAT) marquee("Unit defeated", "UNIT-DEFEATED.webp", 6600);
                    else playEffect(command);
                }).show();
    }

    private void dismissEffect() {
        if (actionEffect != null) {
            ((android.view.ViewGroup)actionEffect.getParent()).removeView(actionEffect);
            if(hangars!=null)hangars.parkDoors();
            actionEffect.destroy();
            actionEffect = null;
        }
    }

    void garrisonDefeated(int actor) { select(actor); playEffect(Command.DEFEAT); }
    private void playEffect(Command command) {
        overlay(command.effectName, owner(), 3100, null, command.page, EffectPlacement.CARD);
    }
    void goalEffect(int side, int points) {
        String body = "<img src='VICTORY-STANDARD.webp' alt=''><strong class='garrison-notice'>SCENARIO GOAL<small>PLAYER "+(side+1)+" · +" + points + " VP</small></strong>";
        overlay("Victory Standard", side, 3100, "<link rel='stylesheet' href='action-effect.css'><body style='--accent:#f6d56c;--duration:2s'>" + body, null, EffectPlacement.FOOTER);
    }
    void unitDefeated(int id) {
        select(id);
        marquee("Unit defeated", "UNIT-DEFEATED.webp", 6600);
    }
    private void marquee(String name, String art, int millis) {
        overlay(name, owner(), millis, "<style>body{margin:0;display:grid;place-items:center;height:100vh;animation:shade "+millis+"ms both}img{width:100%;height:auto}@keyframes shade{0%,100%{background:transparent}10%,90%{background:rgba(0,0,0,.88)}}</style><body><img src='" + art + "'>", null, EffectPlacement.SCREEN);
    }
    private void overlay(String name, int side, int millis, String html, String page, EffectPlacement placement) {
        dismissEffect();
        WebView effect = new WebView(this) {
            @Override protected void onMeasure(int widthSpec,int heightSpec) {
                if(placement==EffectPlacement.CARD && card.getDrawable()!=null){
                    // Fit the effect inside the actual printed card, including letterboxing.
                    int w=Math.min(dp(430),MeasureSpec.getSize(widthSpec)-card.getPaddingLeft()-card.getPaddingRight());
                    int h=Math.min(dp(265),MeasureSpec.getSize(heightSpec)-card.getPaddingTop()-card.getPaddingBottom());
                    int artWidth=card.getDrawable().getIntrinsicWidth(),artHeight=card.getDrawable().getIntrinsicHeight();
                    float scale=Math.min(w/(float)artWidth,h/(float)artHeight);
                    widthSpec=MeasureSpec.makeMeasureSpec(Math.max(1,Math.round(artWidth*scale)),MeasureSpec.EXACTLY);
                    heightSpec=MeasureSpec.makeMeasureSpec(Math.max(1,Math.round(artHeight*scale)),MeasureSpec.EXACTLY);
                }
                super.onMeasure(widthSpec,heightSpec);
            }
            @Override public boolean onTouchEvent(android.view.MotionEvent event) { return false; }
        };
        effect.setFocusable(false);
        actionEffect = effect;
        effect.setBackgroundColor(0);
        effect.setContentDescription(name);
        if(placement==EffectPlacement.CARD){
            effect.setVerticalScrollBarEnabled(false);
            effect.setHorizontalScrollBarEnabled(false);
            cardStage.addView(effect,new FrameLayout.LayoutParams(-1,-1,Gravity.CENTER));
            effect.addOnLayoutChangeListener(new View.OnLayoutChangeListener(){
                @Override public void onLayoutChange(View v,int l,int t,int r,int b,int oldL,int oldT,int oldR,int oldB){
                    if(r<=l || b<=t)return;
                    v.removeOnLayoutChangeListener(this);
                    v.post(()->{
                        if(actionEffect!=v)return;
                        int[] origin=new int[2];
                        consoleViewport.getLocationInWindow(origin);
                        int top=origin[1]+consoleViewport.getPaddingTop();
                        int bottom=origin[1]+consoleViewport.getHeight()-consoleViewport.getPaddingBottom();
                        v.getLocationInWindow(origin);
                        int effectTop=origin[1],effectBottom=effectTop+v.getHeight();
                        if(effectTop<top || effectBottom>bottom)
                            consoleViewport.scrollBy(0,(effectTop+effectBottom-top-bottom)/2);
                    });
                }
            });
        }else if(placement==EffectPlacement.FOOTER){
            FrameLayout.LayoutParams bounds=new FrameLayout.LayoutParams(Math.min(screen.getWidth(),dp(430)),
                    Math.min(screen.getHeight()/2,dp(265)),Gravity.BOTTOM|Gravity.CENTER_HORIZONTAL);
            bounds.bottomMargin=dp(8)+(screen.getRootWindowInsets()==null?0:screen.getRootWindowInsets().getSystemWindowInsetBottom());
            screen.addView(effect,bounds);
        }else screen.addView(effect,new FrameLayout.LayoutParams(-1,-1));
        effect.setWebViewClient(new WebViewClient() {
            @Override public void onPageFinished(WebView view, String url) {
                view.postDelayed(() -> { if (actionEffect == view) dismissEffect(); }, millis);
            }
        });
        if (html == null) effect.loadUrl("file:///android_asset/" + page+"#p"+(side+1));
        else effect.loadDataWithBaseURL("file:///android_asset/", "<meta name=viewport content='width=device-width,initial-scale=1'>" + html, "text/html", "UTF-8", null);
    }

    private void refreshTimeline() {
        PyObject match = session.get("match");
        for (int side=0;side<2;side++){
            int vp=match.callAttr("total",side).toInt();totals[side].setText(String.format(java.util.Locale.ROOT,"%02d",vp));
            if(android.os.Build.VERSION.SDK_INT>=30)totals[side].setStateDescription(vp+" victory points");
        }
        int phase=match.get("phase").toInt();
        int phases=match.get("phases").toInt();
        android.text.SpannableStringBuilder leds=new android.text.SpannableStringBuilder("PHASE  ");
        int first=Math.max(1,Math.min(phase-2,phases-4)),last=Math.min(phases,first+4);
        if(first>1) leds.append("… ");
        for(int n=first;n<=last;n++){
            leds.append(String.valueOf(n)).append(" ");int start=leds.length();
            leds.append(n==phase?"●":"○");
            int color=n==phases?(n==phase?0xffff7566:0xffb47870):(n==phase?0xffa1eb75:0xff789b77);
            leds.setSpan(new android.text.style.ForegroundColorSpan(color),start,leds.length(),android.text.Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);leds.append("  ");
        }
        if(last<phases)leds.append("…");
        phaseLights.setText(leds);phaseLights.setContentDescription("Phase "+phase+" of "+phases);
        timeline.showUnits(units(),phase,match.get("round").toInt());
        timeline.highlight(selected);
    }

    int dp(int n) { return Math.round(n * getResources().getDisplayMetrics().density); }
    private void select(int id) {
        if(id!=selected && actionEffect!=null && actionEffect.getParent()==cardStage)dismissEffect();
        selected=id;timeline.highlight(id);refresh(true);
    }
    private Button footerButton(LinearLayout row, String text, Runnable action) {
        return addButton(row, text, action, ConsoleSkin.button(this, ConsoleSkin.COMPACT_FACE_INSET_DP), 48);
    }
    private Button button(LinearLayout row, String text, Runnable action) {
        return addButton(row, text, action, ConsoleSkin.button(this), 46);
    }
    private Button addButton(LinearLayout row, String text, Runnable action, Button b, int heightDp) {
        b.setText(text);
        b.setOnClickListener(v -> action.run());
        row.addView(b, new LinearLayout.LayoutParams(0, dp(heightDp), 1));
        return b;
    }
    private void counter(LinearLayout panel,String name,int start){
        boolean health=name.equals("HP");
        String field=health?"hp":"energy";
        LinearLayout group=new LinearLayout(this);group.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-2,-1);
        if(!health)p.leftMargin=dp(6);panel.addView(group,p);
        for(int i=0;i<2;i++){
            int delta=i==0?-1:1;
            Button b=ConsoleSkin.button(this);vitalSteps[start+i]=b;
            b.setText(delta<0?"−":"+");b.setTextSize(20);b.setContentDescription((delta<0?"Decrease ":"Increase ")+name);
            b.setOnClickListener(v->save("change",selected,field,delta));group.addView(b,dp(44),dp(48));
            if(i==0){
                ImageView icon=new ImageView(this);icon.setScaleType(ImageView.ScaleType.FIT_CENTER);
                icon.setImageDrawable(ConsoleSkin.art(this,"unit-tokens/"+field+".png"));group.addView(icon,dp(23),dp(23));
            }
        }
    }
    private void refresh(boolean loadArt) {
        PyObject unit = session.callAttr("unit", selected);
        PyObject details = unit.get("card");
        String name = details.get("name").toString();
        boolean deployed = unit.get("deployed").toBoolean();
        deploy.setText(deployed ? "Deployed" : "Deploy");
        boolean live = active();
        deploy.setEnabled(live && !deployed);
        timeline.updateScheduleLink(live,unit.get("label").toString());
        previous.setEnabled(live && match().callAttr("adjacent_cursor",-1)!=null);
        next.setEnabled(live && match().callAttr("adjacent_cursor",1)!=null);
        service.setEnabled(true);
        java.util.List<PyObject> weapons=live && deployed?read("attacks",selected).asList():java.util.Collections.emptyList();
        card.setWeapons(weapons);
        weaponHint.setVisibility(weapons.isEmpty() ? View.INVISIBLE : View.VISIBLE);
        attack.setEnabled(!weapons.isEmpty());
        // Keep the action row stable for matches that use a remote system.
        if (squadHasRemoteSystems) {
            remote.setVisibility(read("systems", selected).asList().isEmpty() ? View.INVISIBLE : View.VISIBLE);
        } else {
            remote.setVisibility(View.GONE);
        }
        remote.setEnabled(live && deployed);
        remote.setText(menus.remoteLabel());
        for(Button b:goals) b.setEnabled(live);
        finishMatch.setEnabled(live);
        undo.setEnabled(session.get("store").callAttr("can_undo").toBoolean());
        String clockLabel=live?"Phase "+match().get("phase")+" · Round "+match().get("round")
                :playerName(match().get("winner").toInt())+" wins";
        matchMenu.setContentDescription(clockLabel);
        matchMenu.setSingleLine();matchMenu.setEllipsize(android.text.TextUtils.TruncateAt.END);
        matchMenu.setText(live?String.format(java.util.Locale.ROOT,"Round %02d",match().get("round").toInt()):clockLabel);
        boolean[] deployedSide={false,false};
        for(PyObject actor:units()) if(actor.get("deployed").toBoolean()) deployedSide[actor.get("player").toInt()]=true;
        for(Button b:unitActions) b.setEnabled(live && deployedSide[(Integer)b.getTag()]);
        title.setText(unit.get("label").toString());
        title.setTextColor(session.callAttr("unit", selected).get("player").toInt() == 0 ? 0xff77d6c1 : 0xffff9b88);
        int health=unit.get("hp").toInt(),en=unit.get("energy").toInt();
        vitalSteps[0].setEnabled(live && health>0);vitalSteps[1].setEnabled(live && health<details.get("hp").toInt());
        vitalSteps[2].setEnabled(live && en>0);vitalSteps[3].setEnabled(live && en<Integer.MAX_VALUE);
        hangars.refresh();
        if (loadArt) {
            try (InputStream in = getAssets().open(details.get("image").toString())) {
                card.setImageBitmap(BitmapFactory.decodeStream(in));
                card.setContentDescription(name + " Unit Card");
            } catch (IOException ex) { throw new IllegalStateException(ex); }
        }
    }
    @Override protected void onResume() {
        super.onResume();
        TabletDisplay.apply(this);
    }

    @Override protected void onSaveInstanceState(Bundle out) {
        super.onSaveInstanceState(out);
        out.putInt("selected", selected);
        if(menus!=null && sortie==null && battlefield==null){
            Bundle draft=menus.bayDraft();
            if(draft!=null){out.putBundle("bay",draft);out.putLong("bayRevision",session.get("revision").toLong());}
        }
    }
    @Override protected void onDestroy() {
        dismissEffect();
        closeBattlefield();
        if(menus!=null)menus.closeService();
        if (session != null) session.callAttr("close");
        super.onDestroy();
    }
}
