import socket

from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings


# SQLAlchemy 2.1 defaults to psycopg 3 for bare PostgreSQL URLs.
# This backend explicitly uses the psycopg2-binary driver in requirements.txt.
database_url = make_url(settings.DATABASE_URL)
if database_url.drivername in {"postgres", "postgresql"}:
    database_url = database_url.set(drivername="postgresql+psycopg2")

engine = create_engine(database_url, pool_pre_ping=True)
@event.listens_for(engine, "do_connect")
def resolve_neon_host(dialect, connection_record, connection_args, connection_params):
    """Use optional fallback DNS only when the local resolver cannot reach Neon."""
    host = connection_params.get("host", "")
    if (
        dialect.driver != "psycopg2"
        or not settings.NEON_DNS_SERVERS
        or not host.endswith(".neon.tech")
        or connection_params.get("hostaddr")
    ):
        return
    connection_params.setdefault("connect_timeout", 15)
    try:
        socket.getaddrinfo(host, connection_params.get("port", 5432), type=socket.SOCK_STREAM)
    except socket.gaierror:
        import dns.resolver

        resolver = dns.resolver.Resolver(configure=False)
        resolver.nameservers = [server.strip() for server in settings.NEON_DNS_SERVERS.split(",") if server.strip()]
        addresses = resolver.resolve(host, "A", lifetime=5)
        # Keep host unchanged for TLS/SNI; libpq uses hostaddr for the TCP connection.
        connection_params["hostaddr"] = str(addresses[0])


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
