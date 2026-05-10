CREATE TABLE "search_logs" (
	"id" serial PRIMARY KEY,
	"user_id" integer,
	"query" text NOT NULL,
	"portales_searched" text,
	"result_count" integer DEFAULT 0 NOT NULL,
	"created_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "stripe_events" (
	"id" serial PRIMARY KEY,
	"event_id" text NOT NULL UNIQUE,
	"event_type" text NOT NULL,
	"user_id" integer,
	"data" text,
	"processed" boolean DEFAULT false NOT NULL,
	"created_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "users" (
	"id" serial PRIMARY KEY,
	"email" text NOT NULL UNIQUE,
	"full_name" text,
	"hashed_password" text,
	"google_id" text UNIQUE,
	"oauth_provider" text,
	"subscription_plan" text DEFAULT 'free' NOT NULL,
	"subscription_id" text,
	"subscription_expires" timestamp,
	"is_active" boolean DEFAULT true NOT NULL,
	"search_count" integer DEFAULT 0 NOT NULL,
	"last_search_date" timestamp,
	"created_at" timestamp DEFAULT now(),
	"updated_at" timestamp DEFAULT now()
);
--> statement-breakpoint
ALTER TABLE "search_logs" ADD CONSTRAINT "search_logs_user_id_users_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id");