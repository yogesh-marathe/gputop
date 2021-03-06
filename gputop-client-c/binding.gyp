{
  "variables": {
    "system_headers%": '<!(node -e "console.log(require(\'path\').resolve(require.resolve(\'gputop-system-headers\'), \'..\'));")'
  },
  "targets": [
    {
      "target_name": "gputop-client-c",
      "defines": [
        "GPUTOP_CLIENT"
      ],
      "include_dirs": [
        ".",
        "<(system_headers)"
      ],
      "cflags": [
          "-std=c11"
      ],
      "sources": [
        "oa-hsw.h",
        "oa-hsw.c",
        "oa-bdw.h",
        "oa-bdw.c",
        "oa-chv.h",
        "oa-chv.c",
        "oa-sklgt2.h",
        "oa-sklgt2.c",
        "oa-sklgt3.h",
        "oa-sklgt3.c",
        "oa-sklgt4.h",
        "oa-sklgt4.c",
        "oa-bxt.h",
        "oa-bxt.c",
        "gputop-oa-counters.h",
        "gputop-oa-counters.c",
        "gputop-client-c-runtime.h",
        "gputop-client-c-runtime.c",
        "gputop-client-c-runtime-bindings.cpp",
        "gputop-client-c.c",
        "gputop-client-c-bindings.h",
        "gputop-client-c-bindings.cpp",
      ],
    }
  ]
}
