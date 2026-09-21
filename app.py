import os
from datetime import datetime, date, timedelta
from flask import Flask, jsonify, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import requests

db = SQLAlchemy()
API_BASE = os.getenv("EXCHANGE_API_BASE", "https://api.frankfurter.app")

CURRENCIES = {
    "USD":"US Dollar","EUR":"Euro","GBP":"British Pound","INR":"Indian Rupee",
    "JPY":"Japanese Yen","CHF":"Swiss Franc","CAD":"Canadian Dollar","AUD":"Australian Dollar",
    "SGD":"Singapore Dollar","AED":"UAE Dirham","CNY":"Chinese Yuan","NZD":"New Zealand Dollar",
    "SEK":"Swedish Krona","NOK":"Norwegian Krone","DKK":"Danish Krone","HKD":"Hong Kong Dollar",
    "ZAR":"South African Rand","BRL":"Brazilian Real","MXN":"Mexican Peso","KRW":"South Korean Won"
}

class User(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    name=db.Column(db.String(80), nullable=False)
    email=db.Column(db.String(160), unique=True, nullable=False)
    password_hash=db.Column(db.String(255), nullable=False)

class Watchlist(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    user_id=db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    base=db.Column(db.String(3), nullable=False)
    quote=db.Column(db.String(3), nullable=False)
    target=db.Column(db.Float, nullable=True)
    created_at=db.Column(db.DateTime, default=datetime.utcnow)

class SavedConversion(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    user_id=db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    base=db.Column(db.String(3), nullable=False)
    quote=db.Column(db.String(3), nullable=False)
    amount=db.Column(db.Float, nullable=False)
    result=db.Column(db.Float, nullable=False)
    created_at=db.Column(db.DateTime, default=datetime.utcnow)

class TravelBudget(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    user_id=db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    destination=db.Column(db.String(80), nullable=False)
    home_currency=db.Column(db.String(3), nullable=False)
    travel_currency=db.Column(db.String(3), nullable=False)
    budget=db.Column(db.Float, nullable=False)
    days=db.Column(db.Integer, nullable=False)
    converted=db.Column(db.Float, nullable=False)
    created_at=db.Column(db.DateTime, default=datetime.utcnow)

def create_app(test_config=None):
    app=Flask(__name__, instance_relative_config=True)
    app.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY","RatePilot-dev-secret-change-me"),
        SQLALCHEMY_DATABASE_URI="sqlite:///"+os.path.join(app.instance_path,"RatePilot.db"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    if test_config: app.config.update(test_config)
    os.makedirs(app.instance_path, exist_ok=True)
    db.init_app(app)
    with app.app_context(): db.create_all()

    def api_get(path, params=None):
        try:
            r=requests.get(API_BASE+path, params=params, timeout=8)
            r.raise_for_status()
            return r.json()
        except Exception:
            return None

    def rate(base, quote):
        if base==quote: return 1.0
        data=api_get("/latest", {"from":base,"to":quote})
        return float(data["rates"][quote]) if data and quote in data.get("rates",{}) else None

    @app.context_processor
    def inject():
        return {"currencies":CURRENCIES, "year":datetime.now().year,
                "logged_in":bool(session.get("user_id")), "user_name":session.get("user_name")}

    @app.get("/")
    def home():
        pairs=[("USD","INR"),("EUR","USD"),("GBP","USD"),("USD","JPY")]
        snapshots=[]
        for b,q in pairs:
            r=rate(b,q)
            snapshots.append({"base":b,"quote":q,"rate":r})
        return render_template("home.html", snapshots=snapshots)

    @app.get("/converter")
    def converter():
        return render_template("converter.html")

    @app.get("/markets")
    def markets():
        return render_template("markets.html")

    @app.get("/trends")
    def trends():
        return render_template("trends.html")

    @app.get("/compare")
    def compare():
        return render_template("compare.html")

    @app.get("/travel")
    def travel():
        budgets=TravelBudget.query.filter_by(user_id=session["user_id"]).order_by(TravelBudget.created_at.desc()).all() if session.get("user_id") else []
        return render_template("travel.html", budgets=budgets)

    @app.route("/watchlist", methods=["GET","POST"])
    def watchlist():
        if not session.get("user_id"):
            flash("Sign in to save a personal watchlist.")
            return redirect(url_for("login", next=request.path))
        if request.method=="POST":
            base=request.form.get("base","USD").upper(); quote=request.form.get("quote","INR").upper()
            target=request.form.get("target")
            if base not in CURRENCIES or quote not in CURRENCIES or base==quote:
                flash("Choose two different supported currencies."); return redirect(url_for("watchlist"))
            existing=Watchlist.query.filter_by(user_id=session["user_id"],base=base,quote=quote).first()
            if not existing:
                db.session.add(Watchlist(user_id=session["user_id"],base=base,quote=quote,target=float(target) if target else None))
                db.session.commit()
            flash("Pair added to Rate Watch.")
            return redirect(url_for("watchlist"))
        items=Watchlist.query.filter_by(user_id=session["user_id"]).order_by(Watchlist.created_at.desc()).all()
        rows=[]
        for x in items: rows.append((x,rate(x.base,x.quote)))
        return render_template("watchlist.html", rows=rows)

    @app.post("/watchlist/<int:item_id>/delete")
    def delete_watch(item_id):
        if not session.get("user_id"): return jsonify(ok=False),401
        x=db.session.get(Watchlist,item_id)
        if not x or x.user_id!=session["user_id"]: return jsonify(ok=False),404
        db.session.delete(x); db.session.commit()
        return jsonify(ok=True)

    @app.route("/login", methods=["GET","POST"])
    def login():
        if request.method=="POST":
            u=User.query.filter_by(email=request.form.get("email","").strip().lower()).first()
            if u and check_password_hash(u.password_hash,request.form.get("password","")):
                session["user_id"]=u.id; session["user_name"]=u.name
                return redirect(request.args.get("next") or url_for("home"))
            flash("Email or password is incorrect.")
        return render_template("auth.html", mode="login")

    @app.route("/register", methods=["GET","POST"])
    def register():
        if request.method=="POST":
            name=request.form.get("name","").strip(); email=request.form.get("email","").strip().lower(); pw=request.form.get("password","")
            if not name or not email or len(pw)<6: flash("Enter a name, valid email, and password of at least 6 characters."); return render_template("auth.html",mode="register")
            if User.query.filter_by(email=email).first(): flash("An account with that email already exists."); return render_template("auth.html",mode="register")
            u=User(name=name,email=email,password_hash=generate_password_hash(pw)); db.session.add(u); db.session.commit()
            session["user_id"]=u.id; session["user_name"]=u.name
            return redirect(url_for("home"))
        return render_template("auth.html", mode="register")

    @app.get("/logout")
    def logout():
        session.clear(); return redirect(url_for("home"))

    @app.get("/api/rate")
    def api_rate():
        base=request.args.get("base","USD").upper(); quote=request.args.get("quote","INR").upper()
        if base not in CURRENCIES or quote not in CURRENCIES: return jsonify(error="Unsupported currency"),400
        r=rate(base,quote)
        if r is None: return jsonify(error="Rate service unavailable"),503
        return jsonify(base=base,quote=quote,rate=r,updated=datetime.utcnow().isoformat()+"Z")

    @app.get("/api/history")
    def api_history():
        base=request.args.get("base","USD").upper(); quote=request.args.get("quote","INR").upper()
        days=int(request.args.get("days","30"))
        if base not in CURRENCIES or quote not in CURRENCIES: return jsonify(error="Unsupported currency"),400
        end=date.today(); start=end-timedelta(days=max(1,min(days,365)))
        data=api_get(f"/{start.isoformat()}..{end.isoformat()}",{"from":base,"to":quote})
        if not data: return jsonify(error="Historical data unavailable"),503
        points=[{"date":d,"rate":v} for d,v in sorted(((d,float(vals[quote])) for d,vals in data.get("rates",{}).items()), key=lambda z:z[0])]
        return jsonify(base=base,quote=quote,points=points)

    @app.get("/api/currencies")
    def api_currencies(): return jsonify(currencies=CURRENCIES)

    @app.get("/api/search")
    def api_search():
        q=request.args.get("q","").lower().strip()
        results=[{"code":c,"name":n} for c,n in CURRENCIES.items() if q in c.lower() or q in n.lower()][:10]
        return jsonify(results=results)

    @app.post("/api/save-conversion")
    def save_conversion():
        if not session.get("user_id"): return jsonify(error="Login required"),401
        try:
            amount=float(request.form["amount"]); result=float(request.form["result"])
            b=request.form["base"].upper(); q=request.form["quote"].upper()
            db.session.add(SavedConversion(user_id=session["user_id"],base=b,quote=q,amount=amount,result=result)); db.session.commit()
            return jsonify(ok=True)
        except Exception: return jsonify(error="Invalid conversion"),400

    @app.post("/travel/save")
    def save_travel():
        try:
            dest=request.form["destination"].strip(); home=request.form["home"].upper(); travel=request.form["travel"].upper()
            budget=float(request.form["budget"]); days=int(request.form["days"]); r=rate(home,travel)
            if not dest or budget<=0 or days<=0 or r is None: raise ValueError()
            converted=budget*r
            if session.get("user_id"):
                x=TravelBudget(user_id=session["user_id"],destination=dest,home_currency=home,travel_currency=travel,budget=budget,days=days,converted=converted)
                db.session.add(x); db.session.commit()
            return jsonify(ok=True, converted=converted, rate=r, saved=bool(session.get("user_id")))
        except Exception: return jsonify(error="Could not calculate budget"),400

    return app

app=create_app()
if __name__=="__main__":
    app.run(debug=True)
