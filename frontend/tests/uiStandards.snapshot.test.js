import { describe, expect, it } from 'vitest';
import {
  pageShell,
  pageHeader,
  pageTitle,
  textBody,
  cardSurface,
  tableSurface,
  buttonPrimary,
  buttonSecondary,
  inputBase,
  modalSurface,
  adminActionToneStyles,
} from '../src/utils/uiStandards';

describe('ui standards snapshot', () => {
  it('keeps shared token contract stable', () => {
    expect({
      pageShell,
      pageHeader,
      pageTitle,
      textBody,
      cardSurface,
      tableSurface,
      buttonPrimary,
      buttonSecondary,
      inputBase,
      modalSurface,
      adminActionToneStyles,
    }).toMatchSnapshot();
  });
});
