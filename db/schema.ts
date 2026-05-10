import {
  pgTable,
  serial,
  text,
  varchar,
  integer,
  boolean,
  timestamp,
  pgEnum,
} from "drizzle-orm/pg-core";

export const subscriptionPlanEnum = pgEnum("subscription_plan", [
  "free",
  "agente",
  "despacho",
  "institucional",
]);

export const users = pgTable("users", {
  id: serial("id").primaryKey(),
  email: varchar("email", { length: 255 }).notNull().unique(),
  fullName: varchar("full_name", { length: 255 }),
  hashedPassword: text("hashed_password"),
  googleId: varchar("google_id", { length: 255 }).unique(),
  oauthProvider: varchar("oauth_provider", { length: 50 }),
  subscriptionPlan: subscriptionPlanEnum("subscription_plan")
    .default("free")
    .notNull(),
  subscriptionId: varchar("subscription_id", { length: 255 }),
  subscriptionExpires: timestamp("subscription_expires"),
  isActive: boolean("is_active").default(true).notNull(),
  searchCount: integer("search_count").default(0).notNull(),
  lastSearchDate: timestamp("last_search_date"),
  createdAt: timestamp("created_at").defaultNow().notNull(),
  updatedAt: timestamp("updated_at").defaultNow().notNull(),
});

export const searchLogs = pgTable("search_logs", {
  id: serial("id").primaryKey(),
  userId: integer("user_id"),
  sessionId: varchar("session_id", { length: 255 }),
  query: text("query").notNull(),
  portalesSearched: text("portales_searched"),
  resultCount: integer("result_count").default(0),
  createdAt: timestamp("created_at").defaultNow().notNull(),
});

export const stripeEvents = pgTable("stripe_events", {
  id: serial("id").primaryKey(),
  eventId: varchar("event_id", { length: 255 }).notNull().unique(),
  eventType: varchar("event_type", { length: 255 }),
  userId: integer("user_id"),
  data: text("data"),
  processed: boolean("processed").default(false),
  createdAt: timestamp("created_at").defaultNow().notNull(),
});
