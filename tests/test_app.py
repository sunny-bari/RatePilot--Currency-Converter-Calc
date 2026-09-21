import os, tempfile, pytest
from app import create_app, db
@pytest.fixture()
def app():
    fd,path=tempfile.mkstemp(); os.close(fd)
    app=create_app({"TESTING":True,"SQLALCHEMY_DATABASE_URI":"sqlite:///"+path,"SECRET_KEY":"test"})
    yield app
    with app.app_context(): db.drop_all()
    os.unlink(path)
@pytest.fixture()
def client(app): return app.test_client()
def test_home(client): assert client.get("/").status_code==200
def test_public_pages(client):
    for p in ["/converter","/markets","/trends","/compare","/travel","/login","/register"]: assert client.get(p).status_code==200
def test_invalid_rate(client): assert client.get("/api/rate?base=XXX&quote=INR").status_code==400
def test_search(client): assert client.get("/api/search?q=Indian").json["results"][0]["code"]=="INR"
def test_login_required_watchlist(client): assert client.get("/watchlist").status_code==302
