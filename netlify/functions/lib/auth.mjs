import * as jose from "jose";
import bcrypt from "bcryptjs";

const SECRET_KEY = Netlify.env.get("SECRET_KEY") || "valuaclick-default-secret-change-in-production";
const ALGORITHM = "HS256";
const ACCESS_TOKEN_EXPIRE_DAYS = 30;

const secret = new TextEncoder().encode(SECRET_KEY);

export async function hashPassword(password) {
  return bcrypt.hashSync(password, 10);
}

export async function verifyPassword(plain, hashed) {
  return bcrypt.compareSync(plain, hashed);
}

export async function createAccessToken(payload) {
  const token = await new jose.SignJWT(payload)
    .setProtectedHeader({ alg: ALGORITHM })
    .setExpirationTime(`${ACCESS_TOKEN_EXPIRE_DAYS}d`)
    .setIssuedAt()
    .sign(secret);
  return token;
}

export async function verifyToken(token) {
  const { payload } = await jose.jwtVerify(token, secret, {
    algorithms: [ALGORITHM],
  });
  return payload;
}

export function createUserToken(userId, email) {
  return createAccessToken({ sub: email, user_id: userId });
}

export async function getTokenData(req) {
  const auth = req.headers.get("authorization");
  if (!auth || !auth.startsWith("Bearer ")) return null;
  const token = auth.slice(7);
  try {
    const payload = await verifyToken(token);
    return { email: payload.sub, userId: payload.user_id };
  } catch {
    return null;
  }
}

export async function requireAuth(req) {
  const data = await getTokenData(req);
  if (!data) {
    throw new Response(JSON.stringify({ detail: "Could not validate credentials" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    });
  }
  return data;
}
