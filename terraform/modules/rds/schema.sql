-- ---------------------------------------------------------------------------
-- Shared schema for the grupo33 microservices: users, routes, posts, offers,
-- scores.
--
-- This file is embedded into init_schema.sh.tpl (via templatefile) and applied
-- by a null_resource + local-exec provisioner AFTER the RDS instance is
-- available. The psql connection target is interpolated from the
-- aws_db_instance attributes; the SQL body itself is static.
--
-- The table definitions mirror the SQLAlchemy ORM models of each app:
--   * users    -> users_app/src/adapters/database/models.py     (UserModel)
--   * routes   -> routes_app/src/adapters/database/models.py    (SQLAlchemyRouteModel)
--   * posts    -> posts_app/src/adapters/database/models.py     (Publication)
--   * offers   -> offers_app/src/adapters/database/models.py    (OfferModel)
--   * scores   -> scores_app/src/adapters/database/models.py    (ScoreModel)
--
-- Keep this file in sync with the app models when the schemas evolve.
-- ---------------------------------------------------------------------------

-- ---------------------------------------------------------------------------
-- users_app: Usuario entity (users_app/src/adapters/database/models.py)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id          VARCHAR(36)  NOT NULL,
    username    VARCHAR(100) NOT NULL,
    email       VARCHAR(255) NOT NULL,
    "phoneNumber" VARCHAR(50),
    dni         VARCHAR(50),
    "fullName"  VARCHAR(255),
    password    VARCHAR(255) NOT NULL,
    salt        VARCHAR(255) NOT NULL,
    token       VARCHAR(255),
    status      VARCHAR(32)  NOT NULL,
    "expireAt"  TIMESTAMP,
    "createdAt" TIMESTAMP    NOT NULL,
    "updatedAt" TIMESTAMP    NOT NULL,
    CONSTRAINT users_pkey PRIMARY KEY (id),
    CONSTRAINT uq_users_username UNIQUE (username),
    CONSTRAINT uq_users_email UNIQUE (email)
);

-- ---------------------------------------------------------------------------
-- routes_app: Route entity (routes_app/src/adapters/database/models.py)
-- flightId is unique per journey; bagCost defaults to 0.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS routes (
    id                    VARCHAR(36)  NOT NULL,
    "flightId"            VARCHAR(20)  NOT NULL,
    "sourceAirportCode"   VARCHAR(3)   NOT NULL,
    "sourceCountry"       VARCHAR(100) NOT NULL,
    "destinyAirportCode"  VARCHAR(3)   NOT NULL,
    "destinyCountry"      VARCHAR(100) NOT NULL,
    "bagCost"             INTEGER      NOT NULL DEFAULT 0,
    "plannedStartDate"    TIMESTAMP    NOT NULL,
    "plannedEndDate"      TIMESTAMP    NOT NULL,
    "createdAt"           TIMESTAMP,
    "updatedAt"           TIMESTAMP,
    CONSTRAINT routes_pkey PRIMARY KEY (id),
    CONSTRAINT uq_routes_flight_id UNIQUE ("flightId")
);
CREATE INDEX IF NOT EXISTS ix_routes_id ON routes (id);
CREATE INDEX IF NOT EXISTS ix_routes_flight_id ON routes ("flightId");

-- ---------------------------------------------------------------------------
-- posts_app: Posts entity (posts_app/src/adapters/database/models.py)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS posts (
    id         VARCHAR(36) NOT NULL,
    route_id   VARCHAR(255) NOT NULL,
    user_id    VARCHAR(255) NOT NULL,
    expire_at  TIMESTAMP    NOT NULL,
    created_at TIMESTAMP    NOT NULL,
    CONSTRAINT posts_pkey PRIMARY KEY (id)
);
CREATE INDEX IF NOT EXISTS ix_posts_route_id ON posts (route_id);
CREATE INDEX IF NOT EXISTS ix_posts_user_id ON posts (user_id);

-- ---------------------------------------------------------------------------
-- offers_app: Offer entity (offers_app/src/adapters/database/models.py)
-- size uses the PackageSize enum: LARGE / MEDIUM / SMALL.
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type t WHERE t.typname = 'packagesize') THEN
        CREATE TYPE packagesize AS ENUM ('LARGE', 'MEDIUM', 'SMALL');
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS offers (
    id          UUID         NOT NULL,
    "postId"    UUID         NOT NULL,
    "userId"    UUID         NOT NULL,
    description VARCHAR(140) NOT NULL,
    size        packagesize  NOT NULL,
    fragile     BOOLEAN      NOT NULL,
    offer       NUMERIC(10,2) NOT NULL,
    "createdAt" TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT offers_pkey PRIMARY KEY (id)
);

-- ---------------------------------------------------------------------------
-- scores_app: Score (Utilidad) entity
-- (scores_app/src/adapters/database/models.py)
-- One current score row per offer: offerId is unique. A missing score is the
-- absence of a row (callers read it as score: null).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS scores (
    id          VARCHAR(36)  NOT NULL,
    "offerId"   VARCHAR(36)  NOT NULL,
    value       FLOAT        NOT NULL,
    "createdAt" TIMESTAMP WITH TIME ZONE NOT NULL,
    "updatedAt" TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT scores_pkey PRIMARY KEY (id),
    CONSTRAINT uq_scores_offer_id UNIQUE ("offerId")
);
CREATE INDEX IF NOT EXISTS ix_scores_offer_id ON scores ("offerId");
