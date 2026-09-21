-- ============================================================
-- テスト用の初期データ（ダミープラン・ダミー店舗・サンプルメニュー）
-- 本番投入は行わないこと。ローカル/検証環境専用。
-- ============================================================

insert into plans (code, name, max_menu_items, max_ai_generations_per_month, analytics_enabled, price_jpy)
values
  ('free', 'Free', 10, 10, false, 0),
  ('pro', 'Pro', 100, 300, true, 4980)
on conflict (code) do nothing;

-- Hestiā: 本サービスの最初の有償顧客（パイロット導入店舗）
insert into stores (slug, name, location_name, brand_concept, sns_style_hint, plan_id)
select
  'hestia',
  'Hestiā',
  '栃木県宇都宮市',
  '暖炉・家族をイメージした、あたたかく親しみやすい雰囲気',
  '家族でゆっくりできるイメージを大切にした、親しみやすい文体',
  id
from plans where code = 'pro'
on conflict (slug) do nothing;

-- サンプルメニュー（プロトタイプのcafe_menu_data.pyより一部抜粋）
insert into menu_items (store_id, name, category, price)
select s.id, m.name, m.category, m.price
from stores s
cross join (values
  ('昔ながらのナポリタン', 'food', 950),
  ('ココア(Hot)', 'drink', 550),
  ('シフォンケーキ(プレーン)', 'sweets', 480),
  ('カフェオレ(Ice)', 'drink', 550)
) as m(name, category, price)
where s.slug = 'hestia';

insert into menu_weather_tags (menu_item_id, tag)
select mi.id, t.tag
from menu_items mi
join stores s on s.id = mi.store_id and s.slug = 'hestia'
join (values
  ('昔ながらのナポリタン', '寒い日'),
  ('昔ながらのナポリタン', '雨の日'),
  ('ココア(Hot)', '寒い日'),
  ('ココア(Hot)', '雨の日'),
  ('シフォンケーキ(プレーン)', '猛暑日'),
  ('シフォンケーキ(プレーン)', '暑い日'),
  ('カフェオレ(Ice)', '猛暑日'),
  ('カフェオレ(Ice)', '暑い日')
) as t(name, tag) on t.name = mi.name
on conflict do nothing;

-- 気象タグ判定しきい値（説明書_weathermenu.txtのデフォルト値を踏襲）
insert into weather_tag_rules (store_id, cold_day_max_temp, hot_day_max_temp, heatwave_max_temp, rain_pop_threshold)
select id, 10, 28, 35, 50
from stores where slug = 'hestia'
on conflict (store_id) do nothing;
