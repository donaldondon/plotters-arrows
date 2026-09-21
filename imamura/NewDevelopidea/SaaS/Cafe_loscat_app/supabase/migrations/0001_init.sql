-- ============================================================
-- 設計書: データベース設計
-- マルチテナントSaaS前提のスキーマ初期構築
-- 原則: 全てのテナント固有テーブルに store_id を持たせ、
--       Row Level Security (RLS) でテナント間のデータ分離を強制する。
-- ============================================================

create extension if not exists "pgcrypto";

-- ------------------------------------------------------------
-- plans: プラン定義（機能制限・料金のマスタ）
-- 設計書: データベース設計 / バックエンド設計(5) データ集計API のゲーティング元
-- ------------------------------------------------------------
create table if not exists plans (
  id uuid primary key default gen_random_uuid(),
  code text not null unique,                 -- 'free' | 'pro' など
  name text not null,
  max_menu_items int not null default 20,
  max_ai_generations_per_month int not null default 30,
  analytics_enabled boolean not null default false,
  price_jpy int not null default 0,
  created_at timestamptz not null default now()
);

-- ------------------------------------------------------------
-- stores: テナント（店舗）本体
-- ------------------------------------------------------------
create table if not exists stores (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,                 -- サイネージURL等に使用 (/signage/<slug>)
  name text not null,
  location_name text not null,               -- 天気取得対象地域
  brand_concept text,
  sns_style_hint text,
  plan_id uuid not null references plans(id),
  created_at timestamptz not null default now()
);

-- ------------------------------------------------------------
-- store_users: 店舗とSupabase Authユーザーの紐付け（RLSの基盤）
-- ------------------------------------------------------------
create table if not exists store_users (
  id uuid primary key default gen_random_uuid(),
  store_id uuid not null references stores(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null default 'owner',        -- 'owner' | 'staff' 等、将来の権限拡張用
  created_at timestamptz not null default now(),
  unique (store_id, user_id)
);

-- ------------------------------------------------------------
-- subscriptions: Stripeサブスクリプション状態
-- 設計書: インフラ・運用設計(2) 決済
-- ------------------------------------------------------------
create table if not exists subscriptions (
  id uuid primary key default gen_random_uuid(),
  store_id uuid not null references stores(id) on delete cascade,
  stripe_customer_id text,
  stripe_subscription_id text,
  status text not null default 'trialing',   -- trialing/active/past_due/canceled 等
  current_period_end timestamptz,
  created_at timestamptz not null default now(),
  unique (store_id)
);

-- ------------------------------------------------------------
-- usage_counters: プラン上限管理用の月間利用カウンタ
-- 設計書: バックエンド設計(3) 外部連携処理（OpenAIコストの一元管理）
-- ------------------------------------------------------------
create table if not exists usage_counters (
  id uuid primary key default gen_random_uuid(),
  store_id uuid not null references stores(id) on delete cascade,
  year_month text not null,                  -- 'YYYY-MM'
  ai_generation_count int not null default 0,
  created_at timestamptz not null default now(),
  unique (store_id, year_month)
);

-- ------------------------------------------------------------
-- menu_items: 店舗ごとのメニュー
-- ------------------------------------------------------------
create table if not exists menu_items (
  id uuid primary key default gen_random_uuid(),
  store_id uuid not null references stores(id) on delete cascade,
  name text not null,
  category text,
  price int,
  is_active boolean not null default true,
  created_at timestamptz not null default now()
);

create index if not exists idx_menu_items_store on menu_items (store_id);

-- ------------------------------------------------------------
-- menu_weather_tags: メニューと気象タグの紐付け（多対多）
-- ------------------------------------------------------------
create table if not exists menu_weather_tags (
  id uuid primary key default gen_random_uuid(),
  menu_item_id uuid not null references menu_items(id) on delete cascade,
  tag text not null check (tag in ('寒い日', '猛暑日', '暑い日', '雨の日', '普通の日')),
  unique (menu_item_id, tag)
);

-- ------------------------------------------------------------
-- weather_tag_rules: 店舗ごとにカスタマイズ可能な気象タグ判定しきい値
-- 設計書: バックエンド設計(4) 天気API連携・判定
-- ------------------------------------------------------------
create table if not exists weather_tag_rules (
  id uuid primary key default gen_random_uuid(),
  store_id uuid not null references stores(id) on delete cascade,
  cold_day_max_temp numeric not null default 10,
  hot_day_max_temp numeric not null default 28,
  heatwave_max_temp numeric not null default 35,
  rain_pop_threshold numeric not null default 50,
  created_at timestamptz not null default now(),
  unique (store_id)
);

-- ------------------------------------------------------------
-- daily_stock: 日次の在庫（メニュー単位）
-- ------------------------------------------------------------
create table if not exists daily_stock (
  id uuid primary key default gen_random_uuid(),
  store_id uuid not null references stores(id) on delete cascade,
  menu_item_id uuid not null references menu_items(id) on delete cascade,
  date date not null,
  available_count int not null default 0,
  priority text check (priority in ('高', '中', '低')),
  created_at timestamptz not null default now(),
  unique (store_id, menu_item_id, date)
);

create index if not exists idx_daily_stock_store_date on daily_stock (store_id, date);

-- ------------------------------------------------------------
-- weather_logs: 取得した天気情報のログ（地域単位でキャッシュ共有可）
-- ------------------------------------------------------------
create table if not exists weather_logs (
  id uuid primary key default gen_random_uuid(),
  location_name text not null,
  date date not null,
  day_label text not null,                   -- '今日' | '明日'
  weather_text text,
  max_temp numeric,
  min_temp numeric,
  am_pop numeric,
  pm_pop numeric,
  fetched_at timestamptz not null default now(),
  unique (location_name, date, day_label)
);

create index if not exists idx_weather_logs_location_date on weather_logs (location_name, date);

-- ------------------------------------------------------------
-- generated_contents: 生成された看板コピー・画像の履歴
-- ------------------------------------------------------------
create table if not exists generated_contents (
  id uuid primary key default gen_random_uuid(),
  store_id uuid not null references stores(id) on delete cascade,
  date date not null,
  signage_text text,
  sns_text text,
  image_url text,
  created_at timestamptz not null default now()
);

create index if not exists idx_generated_contents_store_date on generated_contents (store_id, date);

-- ------------------------------------------------------------
-- sns_posts: SNS自動投稿の履歴
-- 設計書: バックエンド設計(3) 外部連携処理
-- ------------------------------------------------------------
create table if not exists sns_posts (
  id uuid primary key default gen_random_uuid(),
  store_id uuid not null references stores(id) on delete cascade,
  generated_content_id uuid references generated_contents(id) on delete set null,
  platform text not null,                    -- 'instagram' | 'x' 等
  status text not null default 'pending',    -- pending/posted/failed
  posted_at timestamptz,
  created_at timestamptz not null default now()
);

-- ------------------------------------------------------------
-- sales: POS等から取得した売上データ（分析ダッシュボード用）
-- 設計書: バックエンド設計(5) データ集計API / フロントエンド設計(4) 分析ダッシュボード
-- ------------------------------------------------------------
create table if not exists sales (
  id uuid primary key default gen_random_uuid(),
  store_id uuid not null references stores(id) on delete cascade,
  menu_item_id uuid references menu_items(id) on delete set null,
  date date not null,
  quantity int not null default 0,
  amount_jpy int not null default 0,
  source text default 'pos',                 -- 'pos' | 'manual' 等
  created_at timestamptz not null default now()
);

create index if not exists idx_sales_store_date on sales (store_id, date);

-- ------------------------------------------------------------
-- automation_events: Cron等のバッチ処理実行ログ
-- 設計書: インフラ・運用設計(3) 定期実行（Cron）
-- ------------------------------------------------------------
create table if not exists automation_events (
  id uuid primary key default gen_random_uuid(),
  store_id uuid references stores(id) on delete cascade,  -- null許容: 全テナント対象バッチ全体のログも記録可
  event_type text not null,                  -- 'weather_fetch' | 'signage_generate' | 'sns_post' 等
  status text not null default 'success',    -- success/failed
  detail text,
  created_at timestamptz not null default now()
);

-- ============================================================
-- Row Level Security
-- ============================================================

alter table stores enable row level security;
alter table store_users enable row level security;
alter table subscriptions enable row level security;
alter table usage_counters enable row level security;
alter table menu_items enable row level security;
alter table menu_weather_tags enable row level security;
alter table weather_tag_rules enable row level security;
alter table daily_stock enable row level security;
alter table generated_contents enable row level security;
alter table sns_posts enable row level security;
alter table sales enable row level security;
alter table automation_events enable row level security;

-- 例: menu_items は自分の店舗(store_users経由)に属するものだけ参照・編集可能
create policy "menu_items_tenant_isolation"
  on menu_items
  for all
  using (
    exists (
      select 1 from store_users su
      where su.store_id = menu_items.store_id
        and su.user_id = auth.uid()
    )
  )
  with check (
    exists (
      select 1 from store_users su
      where su.store_id = menu_items.store_id
        and su.user_id = auth.uid()
    )
  );

-- 他のテナント固有テーブルにも同様のポリシーを追加していくこと
-- （store_users を経由して auth.uid() が該当店舗に属するかを確認する形を踏襲する）。
