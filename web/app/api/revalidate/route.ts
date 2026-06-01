import { NextRequest, NextResponse } from 'next/server';
import { revalidatePath } from 'next/cache';

// On-demand revalidation endpoint. The pipeline POSTs here at the end of its
// run so the home page picks up the new deck immediately, instead of waiting
// for the time-based ISR window (see `revalidate` in app/page.tsx).
//
// Auth: a shared secret. Set REVALIDATE_SECRET in the Vercel project env, and
// the matching value in the pipeline's environment (GitHub Actions secret).
// The secret may be passed as ?secret=... or an x-revalidate-secret header.
export async function POST(req: NextRequest) {
  const expected = process.env.REVALIDATE_SECRET;
  if (!expected) {
    return NextResponse.json(
      { revalidated: false, message: 'REVALIDATE_SECRET not configured' },
      { status: 500 }
    );
  }

  const provided =
    req.nextUrl.searchParams.get('secret') ??
    req.headers.get('x-revalidate-secret');

  if (provided !== expected) {
    return NextResponse.json(
      { revalidated: false, message: 'Invalid secret' },
      { status: 401 }
    );
  }

  revalidatePath('/');
  return NextResponse.json({ revalidated: true, now: Date.now() });
}
