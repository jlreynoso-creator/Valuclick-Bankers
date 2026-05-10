import { db } from "../../db/index.js";
import { users, searchLogs, stripeEvents } from "../../db/schema.js";
import { eq } from "drizzle-orm";
import {
  hashPassword,
  verifyPassword,
  createUserToken,
  requireAuth,
  getTokenData,
} from "./lib/auth.mjs";

function json(data, status = 200) {
  return Response.json(data, { status });
}

function err(detail, status = 400) {
  return json({ detail }, status);
}

async function handleRegister(req) {
  const { email, password, full_name } = await req.json();
  if (!email || !password || !full_name) return err("Todos los campos son requeridos");

  const existing = await db.select().from(users).where(eq(users.email, email));
  if (existing.length > 0) return err("Email ya registrado");

  const hashed = await hashPassword(password);
  const [user] = await db
    .insert(users)
    .values({
      email,
      fullName: full_name,
      hashedPassword: hashed,
      oauthProvider: "email",
      subscriptionPlan: "free",
    })
    .returning();

  const accessToken = await createUserToken(user.id, user.email);
  return json({ access_token: accessToken, token_type: "bearer", user_id: user.id, email: user.email });
}

async function handleLogin(req) {
  const { email, password } = await req.json();
  if (!email || !password) return err("Email y contraseña requeridos");

  const [user] = await db.select().from(users).where(eq(users.email, email));
  if (!user || !user.hashedPassword) return err("Email o contraseña inválidos", 401);

  const valid = await verifyPassword(password, user.hashedPassword);
  if (!valid) return err("Email o contraseña inválidos", 401);

  const accessToken = await createUserToken(user.id, user.email);
  return json({ access_token: accessToken, token_type: "bearer", user_id: user.id, email: user.email });
}

async function handleGetMe(req) {
  const tokenData = await requireAuth(req);
  const [user] = await db.select().from(users).where(eq(users.id, tokenData.userId));
  if (!user) return err("Usuario no encontrado", 404);

  const isFree = user.subscriptionPlan === "free";
  const remaining = isFree ? Math.max(0, 2 - user.searchCount) : 999;
  const canSearch = isFree ? user.searchCount < 2 : isSubActive(user);

  return json({
    id: user.id,
    email: user.email,
    full_name: user.fullName,
    subscription_plan: user.subscriptionPlan,
    search_count: user.searchCount,
    remaining_free_searches: remaining,
    can_search: canSearch,
  });
}

function isSubActive(user) {
  if (user.subscriptionPlan === "free") return false;
  if (!user.subscriptionExpires) return false;
  return new Date() < new Date(user.subscriptionExpires);
}

async function handleSearch(req) {
  const tokenData = await getTokenData(req);
  if (!tokenData) {
    return json({
      results: [],
      remaining_searches: 0,
      blocked: true,
      message: "Crea una cuenta para buscar. Obtén 2 búsquedas gratuitas.",
    });
  }

  const [user] = await db.select().from(users).where(eq(users.id, tokenData.userId));
  if (!user) return err("Usuario no encontrado", 404);

  const isFree = user.subscriptionPlan === "free";
  const canSearch = isFree ? user.searchCount < 2 : isSubActive(user);

  if (!canSearch) {
    return json({
      results: [],
      remaining_searches: 0,
      blocked: true,
      message: "Límite de búsquedas alcanzado. Suscríbete para acceso ilimitado.",
    });
  }

  const { query, portales } = await req.json();
  const results = [
    {
      id: 1,
      title: `Resultado para: ${query}`,
      price: "$500,000",
      location: "Boca del Río, Veracruz",
      portal: "inmuebles24",
    },
  ];

  await db.insert(searchLogs).values({
    userId: user.id,
    query,
    portalesSearched: JSON.stringify(portales || []),
    resultCount: results.length,
  });

  await db
    .update(users)
    .set({
      searchCount: user.searchCount + 1,
      lastSearchDate: new Date(),
    })
    .where(eq(users.id, user.id));

  const remaining = isFree ? Math.max(0, 2 - (user.searchCount + 1)) : 999;

  return json({
    results,
    remaining_searches: remaining,
    blocked: false,
    message: "Búsqueda exitosa",
  });
}

async function handleSubscriptionStatus(req) {
  const tokenData = await requireAuth(req);
  const [user] = await db.select().from(users).where(eq(users.id, tokenData.userId));
  if (!user) return err("Usuario no encontrado", 404);

  return json({
    plan: user.subscriptionPlan,
    is_active: isSubActive(user),
    expires_at: user.subscriptionExpires,
    search_count: user.searchCount,
    remaining_searches: user.subscriptionPlan === "free" ? Math.max(0, 2 - user.searchCount) : 999,
  });
}

async function handlePricing() {
  return json({
    plans: [
      {
        id: "agente",
        name: "Plan Agente",
        price: 150,
        currency: "MXN",
        period: "monthly",
        features: [
          "Búsquedas ilimitadas",
          "Acceso a todos los portales",
          "Análisis básico",
          "Soporte por email",
        ],
      },
      {
        id: "despacho",
        name: "Plan Despacho",
        price: 300,
        currency: "MXN",
        period: "monthly",
        features: [
          "Búsquedas ilimitadas",
          "Acceso a todos los portales",
          "Análisis avanzado",
          "Reportes PDF",
          "Soporte prioritario",
        ],
      },
      {
        id: "institucional",
        name: "Plan Institucional",
        price: 1000,
        currency: "MXN",
        period: "monthly",
        features: [
          "Búsquedas ilimitadas",
          "Acceso a todos los portales",
          "Análisis enterprise",
          "API custom",
          "Soporte 24/7",
        ],
      },
    ],
  });
}

async function handleStripeWebhook(req) {
  const body = await req.text();
  const sig = req.headers.get("stripe-signature");
  if (!sig) return err("No signature", 400);

  return json({ status: "success", message: "Webhook endpoint ready. Configure Stripe keys to activate." });
}

async function handleHealth() {
  return json({ status: "ok", version: "1.0.0" });
}

export default async (req, context) => {
  const url = new URL(req.url);
  const path = url.pathname.replace(/^\/api/, "").replace(/\/$/, "") || "/";
  const method = req.method;

  try {
    if (path === "/auth/register" && method === "POST") return await handleRegister(req);
    if (path === "/auth/login" && method === "POST") return await handleLogin(req);
    if (path === "/user/me" && method === "GET") return await handleGetMe(req);
    if (path === "/search" && method === "POST") return await handleSearch(req);
    if (path === "/subscription/status" && method === "GET") return await handleSubscriptionStatus(req);
    if (path === "/subscription/checkout" && method === "POST") {
      return json({ message: "Configure Stripe keys to enable checkout." }, 501);
    }
    if (path === "/webhook/stripe" && method === "POST") return await handleStripeWebhook(req);
    if (path === "/pricing" && method === "GET") return await handlePricing();
    if (path === "/health" && method === "GET") return await handleHealth();
    if (path === "/" && method === "GET") return await handleHealth();

    return err("Not found", 404);
  } catch (e) {
    if (e instanceof Response) return e;
    console.error("API Error:", e);
    return err("Internal server error", 500);
  }
};

export const config = {
  path: ["/api/*", "/api"],
};
