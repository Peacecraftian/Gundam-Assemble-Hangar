package app.hangar.prototype;

import android.graphics.*;
import android.graphics.drawable.Drawable;
import android.view.Gravity;
import android.widget.*;
import com.chaquo.python.PyObject;
import java.io.*;
import java.util.*;
import android.widget.LinearLayout.LayoutParams;
import static android.view.View.VISIBLE;
import static android.view.View.GONE;
import static android.widget.LinearLayout.VERTICAL;

final class HangarReadouts {
    private static final String[] KEYS={"strength","speed","shields","Disarm","Slow","Fracture"};
    private static final String[] ICONS={"strength-upgrade","speed-upgrade","shields-upgrade","disarmed-status","slow-status","fractured-status"};
    private static final int[] COLORS={0xff82d6c3,0xffffa18d};
    private final TabletActivity host;
    private final LinearLayout[] tokenRails=new LinearLayout[2];
    LinearLayout rail(int which){return tokenRails[which];}
    private final LinearLayout[] tokens=new LinearLayout[6];
    private final ImageView[] icons=new ImageView[6];
    private final TextView[] counts=new TextView[3];
    private final UnitVitals selectedMeters;
    android.view.View selectedMeters(){return selectedMeters;}
    private final Map<Integer,Tile> tiles=new HashMap<>();
    private final Map<String,Bitmap> banners=new HashMap<>();
    private final ColorMatrixColorFilter reserve;

    HangarReadouts(TabletActivity host) {
        this.host=host;selectedMeters=new UnitVitals(host,true);
        ColorMatrix gray=new ColorMatrix(); gray.setSaturation(0); reserve=new ColorMatrixColorFilter(gray);
        for(int r=0;r<2;r++){tokenRails[r]=new LinearLayout(host);tokenRails[r].setGravity(Gravity.CENTER);tokenRails[r].setOrientation(VERTICAL);}
        for (int i=0;i<KEYS.length;i++) {
            final String key=KEYS[i];
            LinearLayout cell=new LinearLayout(host);cell.setGravity(Gravity.CENTER);
            tokenRails[i/3].addView(cell,new LayoutParams(-1,0,1));
            LinearLayout button=new LinearLayout(host);tokens[i]=button;
            button.setOrientation(VERTICAL);button.setGravity(Gravity.CENTER);
            button.setFocusable(true);button.setPadding(host.dp(3),host.dp(3),host.dp(3),host.dp(3));
            cell.addView(button,new LayoutParams(host.dp(48),host.dp(i<3?52:48)));
            ImageView icon=new ImageView(host);icons[i]=icon;
            icon.setImageDrawable(ConsoleSkin.art(host,"unit-tokens/"+ICONS[i]+".png"));
            icon.setScaleType(ImageView.ScaleType.FIT_CENTER);
            button.addView(icon,host.dp(32),host.dp(31));
            if(i<3){
                TextView count=ConsoleSkin.title(host,"0",11);counts[i]=count;
                count.setTypeface(Typeface.MONOSPACE);count.setIncludeFontPadding(false);
                count.setBackground(ConsoleSkin.plate(host,0xff435052,0xff374345,ConsoleSkin.EDGE));
                button.addView(count,host.dp(31),host.dp(15));
            }
            button.setOnClickListener(v->host.save(Character.isUpperCase(key.charAt(0))?"condition":"upgrade",host.selectedId(),key));
        }
        for(PyObject unit:host.match().get("units").asList())teamSizes[integer(unit,"player")]++;
        for (int side=0;side<2;side++) {
            LinearLayout team=new LinearLayout(host);
            teams[side]=team;team.setOrientation(VERTICAL);
            ConsoleSkin.panel(team,ConsoleSkin.HOUSING[side]);
            team.setPadding(host.dp(4),host.dp(3),host.dp(4),host.dp(4));
            TextView name=ConsoleSkin.title(host,host.playerName(side)+" · Hangar",17);
            name.setTextColor(COLORS[side]);
            Drawable left=ConsoleSkin.art(host,"console/hangar-chevrons.png"),right=ConsoleSkin.art(host,"console/hangar-chevrons.png");
            for(Drawable mark:new Drawable[]{left,right}){mark.setTint(COLORS[side]);mark.setBounds(0,0,host.dp(25),host.dp(10));}
            right.setAutoMirrored(true);if(android.os.Build.VERSION.SDK_INT>=23)right.setLayoutDirection(android.view.View.LAYOUT_DIRECTION_RTL);
            name.setCompoundDrawables(left,null,right,null);team.addView(name,-1,host.dp(36));
            FrameLayout well=new FrameLayout(host);team.addView(well,new LayoutParams(-1,0,1));
            ImageView bay=new ImageView(host);bay.setScaleType(ImageView.ScaleType.CENTER_CROP);
            try(InputStream in=host.getAssets().open("console/Freight Lift.webp")){
                closed[side]=BitmapFactory.decodeStream(in);bay.setImageBitmap(closed[side]);doors[side]=bay;
            } catch(IOException e){throw new IllegalStateException(e);}
            bay.setAlpha(.35f);well.addView(bay,-1,-1);
            ScrollView scroll=new ScrollView(host);scroll.setFillViewport(true);well.addView(scroll,-1,-1);
            LinearLayout strip=new LinearLayout(host);strip.setOrientation(VERTICAL);strip.setGravity(Gravity.CENTER);
            strip.setPadding(0,host.dp(4),0,host.dp(4));scroll.addView(strip);
            java.util.ArrayList<Tile> roster=new java.util.ArrayList<>();
            for (PyObject u:host.match().get("units").asList()) if (integer(u,"player")==side) {
                Tile tile=new Tile(u); roster.add(tile);tiles.put(integer(u,"id"),tile);
                LayoutParams p=new LayoutParams(-1,-2);p.setMargins(0,host.dp(2),0,host.dp(2));strip.addView(tile.frame,p);
            }
            strip.addOnLayoutChangeListener((v,l,t,r,b,ol,ot,or,ob)->fitBanners(scroll,roster));
            scroll.addOnLayoutChangeListener((v,l,t,r,b,ol,ot,or,ob)->fitBanners(scroll,roster));
        }
    }
    private void fitBanners(ScrollView viewport,List<Tile> roster){
        if(viewport.getHeight()<=0 || viewport.getWidth()<=0 || roster.isEmpty())return;
        int rows=Math.max(teamSizes[0],teamSizes[1]);
        int room=Math.min(host.dp(375),viewport.getWidth()-host.dp(24));
        if(room<=0)return;
        int budget=(viewport.getHeight()-host.dp(12))/Math.max(1,rows)-host.dp(32);
        int width=Math.min(room,Math.max(Math.round(room*.74f),Math.round(budget/.195f)));
        int height=Math.round(width*(budget>=width*.228f?.228f:.195f));
        for(Tile tile:roster){
            LayoutParams p=(LayoutParams)tile.frame.getLayoutParams();
            if(p.width!=width){p.width=width;tile.frame.setLayoutParams(p);}
            LayoutParams art=(LayoutParams)tile.picture.getLayoutParams();
            if(art.height!=height){art.height=height;tile.picture.setLayoutParams(art);}
        }
    }
    private final int[] teamSizes=new int[2];
    private final ImageView[] doors=new ImageView[2];
    private final Bitmap[] closed=new Bitmap[2];
    private final LinearLayout[] teams=new LinearLayout[2];
    void openDoor(int side){
        if(android.os.Build.VERSION.SDK_INT<28)return;
        try {
            android.graphics.ImageDecoder.Source source=android.graphics.ImageDecoder.createSource(host.getAssets(),"console/Freight Lift.webp");
            Drawable art=android.graphics.ImageDecoder.decodeDrawable(source);
            if(art instanceof android.graphics.drawable.AnimatedImageDrawable){
                android.graphics.drawable.AnimatedImageDrawable opening=(android.graphics.drawable.AnimatedImageDrawable)art;
                opening.setRepeatCount(0);doors[side].setImageDrawable(opening);opening.start();
            }
        }catch(IOException ignored){doors[side].setImageBitmap(closed[side]);}
    }
    void parkDoors(){
        for(int i=0;i<doors.length;i++){
            Drawable art=doors[i].getDrawable();
            if(art instanceof android.graphics.drawable.Animatable)((android.graphics.drawable.Animatable)art).stop();
            doors[i].setImageBitmap(closed[i]);
        }
    }
    LinearLayout team(int side){return teams[side];}
    private int integer(PyObject u,String field){return u.get(field).toInt();}

    private final class Tile {
        final LinearLayout frame=new LinearLayout(host);
        final ImageView art=new ImageView(host);
        final FrameLayout picture=new FrameLayout(host);
        final Button launch=ConsoleSkin.button(host);
        final TextView shield=ConsoleSkin.title(host,"",11);
        final LinearLayout footer=new LinearLayout(host);
        final UnitVitals meters=new UnitVitals(host,false);
        final LinearLayout conditions=new LinearLayout(host);
        final String name;
        boolean deployed;
        Tile(PyObject u) {
            int id=integer(u,"id"); name=u.get("label").toString();
            frame.setOrientation(VERTICAL);
            frame.setPadding(host.dp(3),host.dp(2),host.dp(3),host.dp(2));
            frame.setOnClickListener(v->host.inspectUnit(id));
            String image=u.get("card").get("image").toString();
            if (!banners.containsKey(image)) try(InputStream in=host.getAssets().open(image)) {
                BitmapFactory.Options opts=new BitmapFactory.Options(); opts.inSampleSize=2;
                Bitmap source=BitmapFactory.decodeStream(in,null,opts);
                banners.put(image,Bitmap.createBitmap(source,0,0,source.getWidth(),Math.max(1,Math.round(source.getHeight()*.322f))));
            } catch(IOException e){throw new IllegalStateException(e);}
            art.setImageBitmap(banners.get(image));
            frame.addView(picture,new LayoutParams(-1,host.dp(56)));
            art.setScaleType(ImageView.ScaleType.MATRIX);picture.addView(art,-1,-1);
            art.addOnLayoutChangeListener((v,l,t,r,b,ol,ot,or,ob)->{
                if(r-l!=or-ol && r>l){
                    Matrix m=new Matrix();float scale=(r-l)/(float)art.getDrawable().getIntrinsicWidth();
                    m.setScale(scale,scale);art.setImageMatrix(m);
                }
            });
            launch.setText("Deploy");ConsoleSkin.primary(launch); launch.setTextSize(12);
            launch.setContentDescription("Deploy "+name);
            launch.setOnClickListener(v->host.deployUnit(id));
            picture.addView(launch,new FrameLayout.LayoutParams(host.dp(58),host.dp(44),Gravity.RIGHT|Gravity.TOP));
            Drawable shieldIcon=ConsoleSkin.art(host,"unit-tokens/shields-upgrade.png");
            shieldIcon.setBounds(0,0,host.dp(19),host.dp(19));
            shield.setCompoundDrawables(shieldIcon,null,null,null);
            shield.setBackground(ConsoleSkin.plate(host,ConsoleSkin.WELL,ConsoleSkin.PANEL,ConsoleSkin.EDGE));
            shield.setPadding(host.dp(2),0,host.dp(3),0);
            picture.addView(shield,new FrameLayout.LayoutParams(-2,host.dp(24),Gravity.RIGHT|Gravity.TOP));
            footer.setGravity(Gravity.BOTTOM);frame.addView(footer,new LayoutParams(-1,-2));
            footer.addView(meters);footer.addView(conditions,new LayoutParams(-2,-2));
            frame.addOnLayoutChangeListener((v,l,t,r,b,ol,ot,or,ob)->{if(r-l!=or-ol)layoutFooter(r-l);});
            layoutFooter(0);

        }
        void layoutFooter(int width){
            int badges=conditions.getChildCount();
            boolean stacked=badges>0 && width-host.dp(44)*badges<host.dp(160);
            int direction=stacked?VERTICAL:LinearLayout.HORIZONTAL;
            if(footer.getOrientation()!=direction)footer.setOrientation(direction);
            LayoutParams p=(LayoutParams)meters.getLayoutParams();
            int target=stacked?-1:0;float weight=stacked?0:1;
            if(p.width!=target||p.weight!=weight||p.height!=host.dp(24)){
                meters.setLayoutParams(new LayoutParams(target,host.dp(24),weight));
            }
            // Keep a 44dp status target while aligning its artwork with the 24dp readout.
            boolean overlap=deployed && !stacked && badges>0;
            LayoutParams band=(LayoutParams)footer.getLayoutParams();
            int top=overlap?-host.dp(20):0;
            if(band.topMargin!=top){band.topMargin=top;footer.setLayoutParams(band);}
            for(int i=0;i<badges;i++){
                android.view.View badge=conditions.getChildAt(i);
                badge.setPadding(host.dp(7),host.dp(overlap?20:7),host.dp(7),host.dp(overlap?1:7));
            }
            conditions.setVisibility(badges==0?GONE:VISIBLE);
        }
        void badge(String label,String icon,Runnable press){
            ImageButton badge=new ImageButton(host);badge.setPadding(host.dp(9),host.dp(9),host.dp(9),host.dp(9));
            badge.setScaleType(ImageView.ScaleType.FIT_CENTER);badge.setBackgroundColor(Color.TRANSPARENT);
            badge.setImageDrawable(ConsoleSkin.art(host,"unit-tokens/"+icon+".png"));badge.setContentDescription(label);
            badge.setEnabled(host.active());badge.setOnClickListener(v->press.run());
            conditions.addView(badge,host.dp(44),host.dp(44));
        }
        void refresh(PyObject u) {
            deployed=u.get("deployed").toBoolean();boolean selected=integer(u,"id")==host.selectedId();
            launch.setVisibility(!deployed && host.active()?VISIBLE:GONE);
            art.setColorFilter(deployed?null:reserve);art.setAlpha(deployed?1f:.58f);
            frame.setBackground(ConsoleSkin.plate(host,ConsoleSkin.WELL,ConsoleSkin.WELL,selected?ConsoleSkin.AMBER:ConsoleSkin.TEAM[integer(u,"player")]));
            String detail="HP "+u.get("hp")+"/"+u.get("card").get("hp")+" · EN "+u.get("energy");
            String state=deployed?"Deployed":"Reserve";
            meters.show(u);
            conditions.removeAllViews();conditions.setGravity(Gravity.CENTER);
            int shields=integer(u,"shield_active");
            shield.setVisibility(shields>0?VISIBLE:GONE);
            if(shields>0){
                shield.setText("×"+shields);shield.setContentDescription("Shield ×"+shields);
                FrameLayout.LayoutParams p=(FrameLayout.LayoutParams)shield.getLayoutParams();
                p.rightMargin=launch.getVisibility()==VISIBLE?host.dp(59):host.dp(2);
                p.topMargin=host.dp(2);shield.setLayoutParams(p);
            }
            for(PyObject effect:u.get("statuses").asList()){
                String key=effect.toString();
                for(int i=3;i<KEYS.length;i++)if(KEYS[i].equals(key)){
                    badge("Clear "+key+" from "+name,ICONS[i],()->host.save("condition",integer(u,"id"),key));break;
                }
            }
            layoutFooter(frame.getWidth());
            frame.setContentDescription(name+" · "+state+" · "+detail);
        }
    }

    void refresh() {
        PyObject selected=host.unit();
        selectedMeters.show(selected);
        for(int i=0;i<KEYS.length;i++) {
            String key=KEYS[i];
            boolean condition=i>=3, on=condition && selected.get("statuses").asList().contains(PyObject.fromJava(key));
            String title=Character.toUpperCase(key.charAt(0))+key.substring(1);
            String value=condition ? title : key.equals("shields") ? String.valueOf(integer(selected,"shield_active")+integer(selected,"shield_spent")) : selected.get(key).toString();
            LinearLayout b=tokens[i];if(!condition)counts[i].setText(value);
            if(android.os.Build.VERSION.SDK_INT>=26)b.setTooltipText(title);
            b.setContentDescription(condition ? title+(on?" active":" clear") : title+" upgrades "+value);
            icons[i].setImageAlpha(condition&&!on?75:255);
            b.setBackground(ConsoleSkin.plate(host,on?0xff453c30:ConsoleSkin.WELL,ConsoleSkin.WELL,on?ConsoleSkin.AMBER:ConsoleSkin.WELL));
            b.setEnabled(host.active() && (!condition || on || selected.get("deployed").toBoolean()));
        }
        for(PyObject u:host.match().get("units").asList()) tiles.get(integer(u,"id")).refresh(u);
    }
}
