/**
 * 1ページ分のネーム生成用型定義。
 * JSON Schema（manga-name-page.schema.json）と整合させる。
 */

/** コマ割りパターン（レイアウト種別） */
export type LayoutType =
  | "single"
  | "vertical_2"
  | "vertical_3"
  | "horizontal_2"
  | "horizontal_3"
  | "grid_2x2"
  | "grid_2x3"
  | "grid_3x2"
  | "top_wide_bottom_two"
  | "left_tall_right_two"
  | "custom";

/** 論文テキスト参照（掛け合いの根拠を追跡） */
export interface SourceTextRef {
  /** 論文からの抜粋（短いフレーズでも可） */
  excerpt: string;
  /** 例: Abstract 2文目、§3.2、Figure 1 キャプション */
  location_label?: string;
  /** 入力テキストに対する文字区間（運用で start/end の開閉を固定） */
  span?: { start: number; end: number };
  link_kind?: "verbatim" | "paraphrase" | "inspired_by";
}

/** 1ページ内の四拍子（コマにレールを付ける） */
export type NarrativeBeat = "起" | "承" | "転" | "結";

/** 1コマ分 */
export interface MangaNamePanel {
  /** 任意。起承転結どの拍に乗せるか（レイアウト提案ロジックと連動） */
  narrative_beat?: NarrativeBeat;
  /** 絵の指示（構図・モチーフ・動き・トーンなど） */
  visual_description: string;
  /** セリフ（モノローグ・ナレーションもここに統合可） */
  dialogue: string;
  /** キャラの表情・感情の指示 */
  character_expression: string;
  /** 博士・助手の掛け合いが参照する論文側の根拠 */
  source_text_ref?: SourceTextRef;
}

/** 1ページ分のネーム */
export interface MangaNamePage {
  page_number: number;
  layout_type: LayoutType;
  /** 任意。layout_type を選んだ理由（AI/人間メモ） */
  layout_rationale?: string;
  /** 読み順で並べたコマ配列 */
  panels: MangaNamePanel[];
}

/** 複数ページをまとめたドキュメント（ルートの title は任意） */
export interface MangaNameStory {
  title?: string;
  pages: MangaNamePage[];
}
