// 設計書: バックエンド設計(2) データ保存API
//
// 動作確認用のヘルスチェックエンドポイント。
// 本格的なAPI（/api/store, /api/menu-items, /api/signup 等）は
// このファイルと同じ /app/api 配下に追加していく。
// store_idは必ずJWT（認証トークン）から導出し、パスパラメータや
// クエリパラメータとして受け取らないこと。

import { NextResponse } from 'next/server';

export async function GET() {
  return NextResponse.json({ status: 'ok' });
}
