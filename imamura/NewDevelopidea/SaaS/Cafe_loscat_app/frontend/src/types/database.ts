// 設計書: バックエンド設計(1) 認証基盤・DB設計 / データベース設計
//
// Supabaseの各テーブルに対応する型定義（雛形）。
// supabase/migrations/0001_init.sql のスキーマと同期させること。
// 本格運用時は `supabase gen types typescript` での自動生成への
// 置き換えを推奨。

export type PlanCode = 'free' | 'pro';

export interface Plan {
  id: string;
  code: PlanCode;
  name: string;
  max_menu_items: number;
  max_ai_generations_per_month: number;
  analytics_enabled: boolean;
  price_jpy: number;
}

export interface Store {
  id: string;
  slug: string;
  name: string;
  location_name: string;
  brand_concept: string | null;
  sns_style_hint: string | null;
  plan_id: string;
  created_at: string;
}

export type WeatherTag = '寒い日' | '猛暑日' | '暑い日' | '雨の日' | '普通の日';

export interface MenuItem {
  id: string;
  store_id: string;
  name: string;
  category: string | null;
  price: number | null;
  is_active: boolean;
  created_at: string;
}

export interface MenuWeatherTag {
  id: string;
  menu_item_id: string;
  tag: WeatherTag;
}

export interface DailyStock {
  id: string;
  store_id: string;
  menu_item_id: string;
  date: string; // YYYY-MM-DD
  available_count: number;
  priority: '高' | '中' | '低' | null;
}
