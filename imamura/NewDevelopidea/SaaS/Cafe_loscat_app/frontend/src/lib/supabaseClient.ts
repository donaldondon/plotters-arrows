// 設計書: バックエンド設計(1) 認証基盤・DB設計
//
// Supabaseクライアントの初期化。
// フロントエンドからはanonキーのみを使用し、store_idの絞り込みは
// Row Level Security（RLS）とJWTに埋め込まれたstore_idに委ねる。
// service_roleキーは絶対にこのファイル（クライアント側）に置かないこと。

import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL as string;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY as string;

if (!supabaseUrl || !supabaseAnonKey) {
  // eslint-disable-next-line no-console
  console.warn(
    '[supabaseClient] NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY が設定されていません。' +
      '.env.local を確認してください。'
  );
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
