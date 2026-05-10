import type { Context } from "@netlify/functions";
import Stripe from "stripe";
import { eq } from "drizzle-orm";
import db from "../../db/index.js";
import { users, stripeEvents } from "../../db/schema.js";
import { jsonResponse, errorResponse } from "./utils/auth.mjs";

export default async function handler(request: Request, _context: Context) {
  if (request.method !== "POST") {
    return errorResponse("Method not allowed", 405);
  }

  const stripeKey = Netlify.env.get("STRIPE_SECRET_KEY");
  const webhookSecret = Netlify.env.get("STRIPE_WEBHOOK_SECRET");
  if (!stripeKey || !webhookSecret) {
    return errorResponse("Stripe not configured", 500);
  }

  const signature = request.headers.get("stripe-signature");
  if (!signature) {
    return errorResponse("No signature", 400);
  }

  const stripe = new Stripe(stripeKey);
  let event: Stripe.Event;

  try {
    const rawBody = await request.text();
    event = stripe.webhooks.constructEvent(rawBody, signature, webhookSecret);
  } catch {
    return errorResponse("Invalid signature", 400);
  }

  if (event.type === "checkout.session.completed") {
    const session = event.data.object as Stripe.Checkout.Session;
    const userId = parseInt(session.metadata?.user_id || "0", 10);
    const plan = session.metadata?.plan;

    if (userId && plan) {
      const expires = new Date();
      expires.setDate(expires.getDate() + 30);

      await db
        .update(users)
        .set({
          subscriptionPlan: plan as "agente" | "despacho" | "institucional",
          subscriptionId: session.subscription as string,
          subscriptionExpires: expires,
          searchCount: 0,
          updatedAt: new Date(),
        })
        .where(eq(users.id, userId));
    }
  } else if (event.type === "customer.subscription.deleted") {
    const subscription = event.data.object as Stripe.Subscription;
    const [user] = await db
      .select()
      .from(users)
      .where(eq(users.subscriptionId, subscription.id))
      .limit(1);

    if (user) {
      await db
        .update(users)
        .set({
          subscriptionPlan: "free",
          subscriptionExpires: null,
          searchCount: 0,
          updatedAt: new Date(),
        })
        .where(eq(users.id, user.id));
    }
  }

  await db.insert(stripeEvents).values({
    eventId: event.id,
    eventType: event.type,
    data: JSON.stringify(event.data),
    processed: true,
  });

  return jsonResponse({ status: "success" });
}

export const config = {
  path: "/api/webhook/stripe",
  method: "POST",
};
