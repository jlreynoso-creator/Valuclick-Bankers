import type { Context } from "@netlify/functions";
import Stripe from "stripe";
import { eq } from "drizzle-orm";
import db from "../../db/index.js";
import { users } from "../../db/schema.js";
import {
  getUserFromRequest,
  jsonResponse,
  errorResponse,
} from "./utils/auth.mjs";

export default async function handler(request: Request, _context: Context) {
  if (request.method !== "POST") {
    return errorResponse("Method not allowed", 405);
  }

  const stripeKey = Netlify.env.get("STRIPE_SECRET_KEY");
  if (!stripeKey) {
    return errorResponse("Stripe not configured", 500);
  }

  const tokenData = await getUserFromRequest(request);
  if (!tokenData) {
    return errorResponse("No autorizado", 401);
  }

  let body: { plan?: string };
  try {
    body = await request.json();
  } catch {
    return errorResponse("Invalid JSON body");
  }

  const { plan } = body;
  const plans: Record<string, string> = {
    agente: "price_agente_valuaclick",
    despacho: "price_despacho_valuaclick",
    institucional: "price_institucional_valuaclick",
  };

  if (!plan || !(plan in plans)) {
    return errorResponse("Plan inválido");
  }

  const [user] = await db
    .select()
    .from(users)
    .where(eq(users.id, tokenData.userId))
    .limit(1);

  if (!user) {
    return errorResponse("Usuario no encontrado", 404);
  }

  try {
    const stripe = new Stripe(stripeKey);
    const frontendUrl =
      Netlify.env.get("FRONTEND_URL") || Netlify.env.get("URL") || "";

    const session = await stripe.checkout.sessions.create({
      customer_email: user.email,
      payment_method_types: ["card"],
      line_items: [{ price: plans[plan], quantity: 1 }],
      mode: "subscription",
      success_url: `${frontendUrl}/success?session_id={CHECKOUT_SESSION_ID}`,
      cancel_url: `${frontendUrl}/#pricing`,
      metadata: {
        user_id: String(user.id),
        plan,
      },
    });

    return jsonResponse({
      checkout_url: session.url,
      session_id: session.id,
    });
  } catch (err) {
    console.error("Stripe error:", err);
    return errorResponse("Error creando sesión de pago", 500);
  }
}

export const config = {
  path: "/api/subscription/checkout",
  method: "POST",
};
