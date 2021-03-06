SUBDIRS =

if SUPPORT_GL
SUBDIRS += registry
endif

bin_PROGRAMS = gputop gputop-system

gputop_SOURCES = gputop-main.c

#gputop_LDADD =
gputop_LDFLAGS = \
    $(GPUTOP_EXTRA_LDFLAGS) \
    -ldl
gputop_CFLAGS = \
    $(GPUTOP_EXTRA_CFLAGS) \
    -std=gnu99
gputop_CPPFLAGS = \
    -I$(top_srcdir) \
    -I$(srcdir)

lib_LTLIBRARIES = libgputop.la
libgputop_la_SOURCES = \
    gputop-hash-table.h \
    gputop-hash-table.c \
    intel_chipset.h \
    oa-hsw.h \
    oa-hsw.c \
    oa-bdw.h \
    oa-bdw.c \
    oa-chv.h \
    oa-chv.c \
    oa-sklgt2.h \
    oa-sklgt2.c \
    oa-sklgt3.h \
    oa-sklgt3.c \
    oa-sklgt4.h \
    oa-sklgt4.c \
    oa-bxt.h \
    oa-bxt.c \
    gputop-perf.h \
    gputop-perf.c \
    gputop-util.h \
    gputop-util.c \
    gputop-list.h \
    gputop-list.c \
    gputop-log.h \
    gputop-log.c \
    gputop-mainloop.h \
    gputop-ncurses.c \
    gputop-cpu.h \
    gputop-cpu.c \
    gputop-debugfs.h \
    gputop-debugfs.c \
    gputop-ioctl.c \
    gputop.pb-c.h \
    gputop.pb-c.c \
    gputop-server.h \
    gputop-server.c
libgputop_la_CFLAGS = \
    $(GPUTOP_EXTRA_CFLAGS) \
    $(PTHREAD_CFLAGS) \
    $(PROTOBUF_DEP_CFLAGS) \
    $(CRYPTO_DEP_CFLAGS) \
    $(SSL_DEP_CFLAGS) \
    -I$(top_srcdir)/libuv/include \
    -I$(top_srcdir)/h2o \
    -I$(top_srcdir)/h2o/include \
    -DGPUTOP_WEB_ROOT=\"$(datadir)/remote\" \
    -std=gnu11
libgputop_la_LIBADD = \
    $(GPUTOP_EXTRA_LDFLAGS) \
    $(PTHREAD_LIBS) \
    $(PROTOBUF_DEP_LIBS) \
    $(YAML_DEP_LIBS) \
    $(CRYPTO_DEP_LIBS) \
    $(SSL_DEP_LIBS) \
    $(top_builddir)/libuv/libuv.la \
    $(top_builddir)/h2o/libh2o.la \
    $(top_builddir)/protobuf-c/libprotobuf-c.la \
    -ldl -lm -lrt

if SUPPORT_GL
libgputop_la_SOURCES += \
    gputop-gl.h \
    gputop-gl.c

# XXX: it's awkward to link libgputop.so with the systen libGL without
# libtool getting confused (it will think we want to link with our
# wrapper libGL.so but doing that introduces a cyclical dependency)
# gputop-gl.c is instead careful to lookup GLX symbols via
# dlopen/dlsym so we don't need to be linked to the system GL library.
#libgputop_la_LIBADD += $(GLX_DEP_LIBS)
libgputop_la_LIBADD += -lX11
libgputop_la_CFLAGS += $(GLX_DEP_CFLAGS)

wrapperdir = $(libdir)/wrappers
wrapper_LTLIBRARIES = libfakeGL.la #libEGL.la

libfakeGL_la_SOURCES = \
    registry/glxapi.c \
    registry/glapi.c
libfakeGL_la_CFLAGS = \
    $(GPUTOP_EXTRA_CFLAGS)
libfakeGL_la_LIBADD = libgputop.la
libfakeGL_la_LDFLAGS = -shared -version-info 1
endif

#libEGL_la_SOURCES = \
#    registry/eglapi.c
#libEGL_la_CFLAGS = \
#    $(GPUTOP_EXTRA_CFLAGS)
#libEGL_la_LIBADD = libgputop.la
#libEGL_la_LDFLAGS = -shared -version-info 1

gputop_system_LDADD = \
    $(GPUTOP_EXTRA_LDFLAGS) \
    libgputop.la
gputop_system_CFLAGS = \
    $(GPUTOP_EXTRA_CFLAGS)
gputop_system_CPPFLAGS = \
    -I$(top_srcdir) \
    -I$(srcdir)

BUILT_SOURCES = \
    oa-hsw.h \
    oa-hsw.c \
    oa-bdw.h \
    oa-bdw.c \
    oa-chv.h \
    oa-chv.c \
    oa-sklgt2.h \
    oa-sklgt2.c \
    oa-sklgt3.h \
    oa-sklgt3.c \
    oa-sklgt4.h \
    oa-sklgt4.c \
    oa-bxt.h \
    oa-bxt.c \
    gputop.pb-c.h \
    gputop.pb-c.c

data_dir = $(top_srcdir)/gputop-data
script_dir = $(top_srcdir)/scripts

oa-%.h oa-%.c: $(data_dir)/oa-%.xml $(script_dir)/gputop-oa-codegen.py
	$(PYTHON2) $(PYTHON_FLAGS) $(script_dir)/gputop-oa-codegen.py \
	    --header=$(builddir)/oa-$(*).h \
	    --code=$(builddir)/oa-$(*).c \
	    --chipset="$(*)" $(data_dir)/oa-$(*).xml

%.pb-c.c %.pb-c.h: $(data_dir)/%.proto
	$(top_builddir)/protoc-c/protoc-c --c_out=$(top_builddir)/gputop-server -I$(data_dir) $(data_dir)/$(*F).proto

CLEANFILES = $(BUILT_SOURCES)
