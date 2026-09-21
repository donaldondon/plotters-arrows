// 設計書: インフラ・運用設計(3) 定期実行（Cron）
//
// 全テナント対象のバッチ処理（例: 毎朝7時に天気取得→おすすめメニュー判定→
// 看板/SNS用テキスト生成→（プラン対象なら）SNS自動投稿）のEdge Function雛形。
// Supabase Edge Functions + pg_cron（またはVercel Cron）からの呼び出しを想定。
//
// 重要: 単一店舗の処理ではなく、stores テーブルを全件走査して
// テナントごとに処理する設計にすること。

// @ts-nocheck
import { serve } from 'https://deno.land/std@0.224.0/http/server.ts';
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2.45.0';

serve(async (_req) => {
  const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
  const serviceRoleKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
  const supabase = createClient(supabaseUrl, serviceRoleKey);

  // 1. 全テナント（stores）を取得
  const { data: stores, error } = await supabase.from('stores').select('id, slug, location_name');
  if (error) {
    return new Response(JSON.stringify({ status: 'error', error: error.message }), { status: 500 });
  }

  const results: { store_id: string; status: string }[] = [];

  for (const store of stores ?? []) {
    try {
      // TODO: 2. store.location_name の天気を取得（weather_logsにキャッシュがあれば再利用）
      // TODO: 3. weather_tag_rules に基づき気象タグを判定
      // TODO: 4. daily_stock からおすすめメニューを選定
      // TODO: 5. usage_counters を確認し、プラン上限内であればOpenAIで文章生成
      // TODO: 6. generated_contents に保存
      // TODO: 7. SNS連携が有効な場合はsns_postsに投稿予約を作成

      results.push({ store_id: store.id, status: 'skipped_not_implemented' });
    } catch (e) {
      results.push({ store_id: store.id, status: 'error' });
      await supabase.from('automation_events').insert({
        store_id: store.id,
        event_type: 'daily_signage_batch',
        status: 'failed',
        detail: String(e),
      });
    }
  }

  return new Response(JSON.stringify({ status: 'ok', results }), {
    headers: { 'Content-Type': 'application/json' },
  });
});
