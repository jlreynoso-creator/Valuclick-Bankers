import type { Context } from "@netlify/functions";
import { eq } from "drizzle-orm";
import db from "../../db/index.js";
import { users } from "../../db/schema.js";
import {
  verifyPassword,
  createAccessToken,
  jsonResponse,
  errorResponse,
} from "./utils/auth.mjs";

export default async function handler(request: Request, _context: Context) {
  if (request.method !== "POST") {
    return errorResponse("Method not allowed", 405);
  }

  let body: { email?: string; password?: string };
  try {
    body = await request.json();
  } catch {
    return errorResponse("Invalid JSON body");
  }

  const { email, password } = body;
  if (!email || !password) {
    return errorResponse("Email y contraseña son requeridos");
  }

  const [user] = await db
    .select()
    .from(users)
    .where(eq(users.email, email))
    .limit(1);

  if (!user || !user.hashedPassword) {
    return errorResponse("Email o contraseña inválidos", 401);
  }

  const valid = await verifyPassword(password, user.hashedPassword);
  if (!valid) {
    return errorResponse("Email o contraseña inválidos", 401);
  }

  const accessToken = await createAccessToken(user.id, user.email);

  return jsonResponse({
    access_token: accessToken,
    token_type: "bearer",
    user_id: user.id,
    email: user.email,
  });
}

export const config = {
  path: "/api/auth/login",
  method: "POST",
};
