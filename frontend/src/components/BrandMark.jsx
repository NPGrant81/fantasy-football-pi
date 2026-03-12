/* ignore-breakpoints */
import { BRAND_LOGO_ALT, BRAND_NAME } from '../constants/branding';

export default function BrandMark({
  containerClassName = 'flex items-center gap-2',
  imageClassName = 'w-8 h-8',
  textClassName = '',
  text = BRAND_NAME,
  textTag = 'span',
}) {
  const TextTag = textTag;

  return (
    <div className={containerClassName}>
      <img
        src={import.meta.env.BASE_URL + 'src/assets/react.svg'}
        alt={BRAND_LOGO_ALT}
        className={imageClassName}
      />
      <TextTag className={textClassName}>{text}</TextTag>
    </div>
  );
}
