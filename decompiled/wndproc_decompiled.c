// WndProc decompiled from 0x004038d0
// Function: FUN_004038d0 size=554


LRESULT FUN_004038d0(HWND param_1,uint param_2,WPARAM param_3,LPARAM param_4)

{
  int iVar1;
  LRESULT LVar2;
  tagPAINTSTRUCT tStack_40;
  
  if (param_2 < 0x201) {
    if (param_2 == 0x200) {
      FUN_004038a0(0,param_3,param_4);
      return 1;
    }
    if (param_2 < 0x101) {
      if (param_2 == 0x100) {
switchD_0040396d_switchD:
        switch(param_3) {
        case 0x25:
          FUN_00402a80(8);
          return 0;
        case 0x26:
          FUN_00402a80(0xb);
          return 0;
        case 0x27:
          FUN_00402a80(0xc);
          return 0;
        case 0x28:
          FUN_00402a80(10);
          return 0;
        default:
          FUN_004023e0();
          return 1;
        }
      }
      if (param_2 == 1) {
        DAT_00418050 = param_1;
        return 1;
      }
      if (param_2 == 2) goto LAB_004039e7;
      if (param_2 == 0xf) {
        DAT_0041804c = BeginPaint(param_1,&tStack_40);
        FUN_004032f0();
        EndPaint(param_1,&tStack_40);
        return 0;
      }
    }
    else {
      if (param_2 == 0x102) {
        iVar1 = FUN_00402a80(param_3);
        if (iVar1 == 0) {
          return 1;
        }
LAB_004039e7:
        PostQuitMessage(0);
        return 1;
      }
      if (param_2 == 0x104) goto switchD_0040396d_switchD;
    }
  }
  else {
    switch(param_2) {
    case 0x201:
      FUN_004038a0(1,param_3,param_4);
      return 1;
    case 0x202:
      FUN_004038a0(4,param_3,param_4);
      return 1;
    case 0x204:
      FUN_004038a0(3,param_3,param_4);
      return 1;
    case 0x205:
      FUN_004038a0(6,param_3,param_4);
      return 1;
    case 0x207:
      FUN_004038a0(2,param_3,param_4);
      return 1;
    case 0x208:
      FUN_004038a0(5,param_3,param_4);
      return 1;
    }
  }
  LVar2 = DefWindowProcA(param_1,param_2,param_3,param_4);
  return LVar2;
}

