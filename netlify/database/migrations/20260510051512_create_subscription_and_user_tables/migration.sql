CREATE TYPE "subscription_plan" AS ENUM('free', 'agente', 'despacho', 'institucional');--> statement-breakpoint
CREATE TABLE "search_logs" (
	"id" serial PRIMARY KEY,
	"user_id" integer,
	"session_id" varchar(255),
	"query" text NOT NULL,
	"portales_searched" text,
	"result_count" integer DEFAULT 0,
	"created_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "stripe_events" (
	"id" serial PRIMARY KEY,
	"event_id" varchar(255) NOT NULL UNIQUE,
	"event_type" varchar(255),
	"user_id" integer,
	"data" text,
	"processed" boolean DEFAULT false,
	"created_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "users" (
	"id" serial PRIMARY KEY,
	"email" varchar(255) NOT NULL UNIQUE,
	"full_name" varchar(255),
	"hashed_password" text,
	"google_id" varchar(255) UNIQUE,
	"oauth_provider" varchar(50),
	"subscription_plan" "subscription_plan" DEFAULT 'free'::"subscription_plan" NOT NULL,
	"subscription_id" varchar(255),
	"subscription_expires" timestamp,
	"is_active" boolean DEFAULT true NOT NULL,
	"search_count" integer DEFAULT 0 NOT NULL,
	"last_search_date" timestamp,
	"created_at" timestamp DEFAULT now() NOT NULL,
	"updated_at" timestamp DEFAULT now() NOT NULL
);
