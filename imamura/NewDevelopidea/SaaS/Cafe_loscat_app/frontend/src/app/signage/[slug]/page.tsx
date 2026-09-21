// 設計書: フロントエンド設計(3) サイネージ用表示画面
//
// 閲覧専用の公開URL（例: /signage/hestia）。
// 認証不要で、店舗ごとのslugから最新のおすすめメニュー・生成画像を
// 全画面表示する。店舗の特定は必ずslug→store_idのサーバー側解決を
// 経由し、クライアントが任意のstore_idを指定できないようにすること。

interface SignagePageProps {
  params: { slug: string };
}

export default function SignagePage({ params }: SignagePageProps) {
  const { slug } = params;

  return (
    <main style={{ width: '100vw', height: '100vh' }}>
      <h1>サイネージ表示（雛形） - 店舗: {slug}</h1>
      <p>ここに最新の看板画像・おすすめメニューを全画面表示する。</p>
    </main>
  );
}
