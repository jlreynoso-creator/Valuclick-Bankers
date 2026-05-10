import { pgTable, serial, text, timestamp, integer, boolean } from "drizzle-orm/pg-core";

export const users = pgTable("users", {
  id: serial().primaryKey(),
  email: text().notNull().unique(),
  fullName: text("full_name"),
  hashedPassword: text("hashed_password"),
  googleId: text("google_id").unique(),
  oauthProvider: text("oauth_provider"),
  subscriptionPlan: text("subscription_plan").notNull().default("free"),
  subscriptionId: text("subscription_id"),
  subscriptionExpires: timestamp("subscription_expires"),
  isActive: boolean("is_active").notNull().default(true),
  searchCount: integer("search_count").notNull().default(0),
  lastSearchDate: timestamp("last_search_date"),
  createdAt: timestamp("created_at").defaultNow(),
  updatedAt: timestamp("updated_at").defaultNow(),
});

export const searchLogs = pgTable("search_logs", {
  id: serial().primaryKey(),
  userId: integer("user_id").references(() => users.id),
  query: text().notNull(),
  portalesSearched: text("portales_searched"),
  resultCount: integer("result_count").notNull().default(0),
  createdAt: timestamp("created_at").defaultNow(),
});

export const stripeEvents = pgTable("stripe_events", {
  id: serial().primaryKey(),
  eventId: text("event_id").notNull().unique(),
  eventType: text("event_type").notNull(),
  userId: integer("user_id"),
  data: text(),
  processed: boolean().notNull().default(false),
  createdAt: timestamp("created_at").defaultNow(),
});
